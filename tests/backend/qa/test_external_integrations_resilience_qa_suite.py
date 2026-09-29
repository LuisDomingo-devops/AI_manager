"""
Suite de QA para resiliencia de integraciones externas.
Prueba ráfagas de fallos, recuperación automática y comportamiento bajo carga.

RQ-012-01..06
"""
import time
import threading
import pytest
from unittest.mock import MagicMock

from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    circuit_breaker,
)


class TestQABurstFailureAndRecovery:
    """QA: Ráfagas de fallos y recuperación automática."""

    def test_full_lifecycle_closed_open_halfopen_closed(self):
        """Ciclo completo: CLOSED → OPEN → HALF_OPEN → CLOSED."""
        cb = CircuitBreaker(
            name="qa_full_lifecycle",
            failure_threshold=3,
            recovery_timeout_seconds=0.1,
        )
        failing = MagicMock(side_effect=ConnectionError("down"))
        success = MagicMock(return_value="recovered")

        # CLOSED: 3 fallos → OPEN
        for _ in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

        # OPEN: rechaza inmediatamente
        failing.reset_mock()
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(failing)
        failing.assert_not_called()

        # Esperar timeout → HALF_OPEN
        time.sleep(0.15)

        # HALF_OPEN → CLOSED al tener éxito
        result = cb.call(success)
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0

    def test_burst_of_ten_failures_then_recovery(self):
        """10 fallos seguidos, luego recuperación tras timeout."""
        cb = CircuitBreaker(
            name="qa_burst_10",
            failure_threshold=5,
            recovery_timeout_seconds=0.1,
        )
        failing = MagicMock(side_effect=Exception("error"))
        success = MagicMock(return_value="ok")

        errors_raised = []
        for _ in range(10):
            try:
                cb.call(failing)
            except (Exception, CircuitBreakerOpenError) as e:
                errors_raised.append(type(e).__name__)

        # Debe haber mezclado ConnectionError (primeros 5) y CircuitBreakerOpenError (los siguientes)
        assert CircuitBreakerOpenError.__name__ in errors_raised
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.15)
        result = cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_half_open_retry_failure_then_second_recovery(self):
        """Fallo en HALF_OPEN → OPEN. Segunda oportunidad tras timeout → CLOSED."""
        cb = CircuitBreaker(
            name="qa_double_recovery",
            failure_threshold=2,
            recovery_timeout_seconds=0.1,
        )
        failing = MagicMock(side_effect=ConnectionError("down"))
        success = MagicMock(return_value="ok")

        # → OPEN
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

        # HALF_OPEN, falla de nuevo → OPEN
        time.sleep(0.15)
        with pytest.raises(ConnectionError):
            cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

        # Segunda recuperación
        time.sleep(0.15)
        result = cb.call(success)
        assert result == "ok"
        assert cb.state == CircuitBreakerState.CLOSED


class TestQAConcurrentAccess:
    """QA: Acceso concurrente seguro al Circuit Breaker."""

    def test_concurrent_failures_are_counted_correctly(self):
        """Múltiples hilos fallando concurrentemente no corrompen el estado."""
        cb = CircuitBreaker(
            name="qa_concurrent",
            failure_threshold=10,
            recovery_timeout_seconds=60,
        )
        failing = MagicMock(side_effect=Exception("concurrent error"))
        results = []

        def do_call():
            try:
                cb.call(failing)
            except Exception:
                results.append("error")

        threads = [threading.Thread(target=do_call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Todos los hilos deben haber registrado un error
        assert len(results) == 10
        # El CB debe estar OPEN (exactamente 10 fallos con threshold=10)
        assert cb.state == CircuitBreakerState.OPEN

    def test_concurrent_calls_blocked_when_open(self):
        """En estado OPEN, múltiples hilos concurrentes reciben CircuitBreakerOpenError."""
        cb = CircuitBreaker(
            name="qa_concurrent_open",
            failure_threshold=2,
            recovery_timeout_seconds=60,
        )
        failing = MagicMock(side_effect=Exception("down"))

        # Abrir el CB
        for _ in range(2):
            with pytest.raises((Exception, CircuitBreakerOpenError)):
                cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

        # Concurrente: todos deben recibir CircuitBreakerOpenError
        not_called_mock = MagicMock(return_value="should_not_run")
        open_errors = []

        def try_call():
            try:
                cb.call(not_called_mock)
            except CircuitBreakerOpenError:
                open_errors.append(True)

        threads = [threading.Thread(target=try_call) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(open_errors) == 5
        not_called_mock.assert_not_called()


class TestQADecoratorRealWorldPattern:
    """QA: Patrón real de uso con decorador en adaptadores."""

    def test_decorated_aeat_adapter_opens_after_failures(self):
        """Simula un adaptador AEAT real decorado con circuit_breaker."""
        call_count = {"n": 0}

        @circuit_breaker(name="qa_aeat_adapter", failure_threshold=3, recovery_timeout_seconds=0.1)
        def enviar_factura_aeat(factura_id: str) -> dict:
            call_count["n"] += 1
            raise ConnectionError(f"AEAT no responde para factura {factura_id}")

        # 3 fallos → abre el CB
        for i in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                enviar_factura_aeat(f"FAC-{i:04d}")

        # Siguiente intento → CircuitBreakerOpenError (sin incrementar call_count)
        count_before = call_count["n"]
        with pytest.raises(CircuitBreakerOpenError):
            enviar_factura_aeat("FAC-9999")
        assert call_count["n"] == count_before, "El CB debe haber bloqueado la llamada real"

    def test_decorated_stripe_adapter_recovers(self):
        """Simula un adaptador Stripe decorado que falla y luego se recupera."""
        responses = iter([
            ConnectionError("Stripe down"),
            ConnectionError("Stripe down"),
            {"charge_id": "ch_123", "status": "succeeded"},  # Recuperación
        ])
        response_for_recovery = {"charge_id": "ch_123", "status": "succeeded"}

        @circuit_breaker(
            name="qa_stripe_adapter_recovery",
            failure_threshold=2,
            recovery_timeout_seconds=0.1,
        )
        def cobrar_con_stripe(amount: float) -> dict:
            response = next(responses, response_for_recovery)
            if isinstance(response, Exception):
                raise response
            return response

        # 2 fallos → OPEN
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cobrar_con_stripe(100.0)

        # Esperar timeout → HALF_OPEN
        time.sleep(0.15)

        # Recuperación
        result = cobrar_con_stripe(100.0)
        assert result["charge_id"] == "ch_123"
        assert result["status"] == "succeeded"


class TestQACircuitBreakerConfiguration:
    """QA: Configuraciones diferentes funcionan correctamente."""

    def test_threshold_1_opens_immediately(self):
        """Con threshold=1, el primer fallo abre el CB."""
        cb = CircuitBreaker(name="qa_threshold_1", failure_threshold=1, recovery_timeout_seconds=60)
        failing = MagicMock(side_effect=Exception("down"))
        with pytest.raises((Exception, CircuitBreakerOpenError)):
            cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

    def test_high_threshold_tolerates_many_failures(self):
        """Con threshold=100, tolera 99 fallos sin abrir."""
        cb = CircuitBreaker(name="qa_threshold_100", failure_threshold=100, recovery_timeout_seconds=60)
        failing = MagicMock(side_effect=Exception("down"))
        for _ in range(99):
            with pytest.raises(Exception):
                cb.call(failing)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 99

    def test_very_short_timeout_allows_quick_recovery(self):
        """Un timeout muy corto (0.01s) permite recuperación casi inmediata."""
        cb = CircuitBreaker(name="qa_short_timeout", failure_threshold=2, recovery_timeout_seconds=0.01)
        failing = MagicMock(side_effect=Exception("down"))
        success = MagicMock(return_value="fast_recovery")

        for _ in range(2):
            with pytest.raises((Exception, CircuitBreakerOpenError)):
                cb.call(failing)
        assert cb.state == CircuitBreakerState.OPEN

        time.sleep(0.05)
        result = cb.call(success)
        assert result == "fast_recovery"
        assert cb.state == CircuitBreakerState.CLOSED
