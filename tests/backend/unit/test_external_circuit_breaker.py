"""
Tests unitarios para el Circuit Breaker.
TDD RED phase: estos tests deben fallar hasta que se implemente circuit_breaker.py

RQ-012-01: Circuit Breaker con 3 estados (CLOSED, OPEN, HALF_OPEN)
RQ-012-02: Transición CLOSED → OPEN tras N fallos consecutivos
RQ-012-03: Transición OPEN → HALF_OPEN tras timeout
RQ-012-04: Retorno rápido en estado OPEN (CircuitBreakerOpenError)
RQ-012-05: Recuperación en HALF_OPEN
RQ-012-06: Decorador @circuit_breaker
"""
import time
import pytest
from unittest.mock import MagicMock, patch


# --- Importaciones bajo test ---
# Deben fallar (RED) hasta que exista circuit_breaker.py
from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
    circuit_breaker,
)


class TestCircuitBreakerInitialState:
    """El CB debe arrancar en estado CLOSED."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(name="test_init", failure_threshold=3, recovery_timeout_seconds=30)
        assert cb.state == CircuitBreakerState.CLOSED

    def test_initial_failure_count_is_zero(self):
        cb = CircuitBreaker(name="test_init_count", failure_threshold=3, recovery_timeout_seconds=30)
        assert cb.failure_count == 0

    def test_name_is_stored(self):
        cb = CircuitBreaker(name="my_service", failure_threshold=3, recovery_timeout_seconds=30)
        assert cb.name == "my_service"


class TestCircuitBreakerClosedToOpen:
    """RQ-012-02: Transición CLOSED → OPEN tras failure_threshold fallos."""

    def test_single_failure_does_not_open(self):
        cb = CircuitBreaker(name="test_c2o_1", failure_threshold=3, recovery_timeout_seconds=30)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        with pytest.raises(ConnectionError):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 1

    def test_two_failures_do_not_open(self):
        cb = CircuitBreaker(name="test_c2o_2", failure_threshold=3, recovery_timeout_seconds=30)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing_func)
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 2

    def test_threshold_failures_open_circuit(self):
        cb = CircuitBreaker(name="test_c2o_3", failure_threshold=3, recovery_timeout_seconds=30)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        for _ in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(name="test_c2o_reset", failure_threshold=3, recovery_timeout_seconds=30)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        success_func = MagicMock(return_value="ok")
        # 2 fallos
        for _ in range(2):
            with pytest.raises(ConnectionError):
                cb.call(failing_func)
        # 1 éxito → debe resetear contador
        result = cb.call(success_func)
        assert result == "ok"
        assert cb.failure_count == 0
        assert cb.state == CircuitBreakerState.CLOSED


class TestCircuitBreakerOpenState:
    """RQ-012-04: En estado OPEN retornar CircuitBreakerOpenError inmediatamente."""

    def test_open_raises_fast_error_without_calling_function(self):
        cb = CircuitBreaker(name="test_open", failure_threshold=3, recovery_timeout_seconds=60)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        # Llevar al estado OPEN
        for _ in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing_func)
        # Resetear el mock para verificar que no se llama más
        failing_func.reset_mock()
        # Ahora debe retornar error rápido SIN llamar a failing_func
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(failing_func)
        failing_func.assert_not_called()

    def test_circuit_breaker_open_error_has_service_name(self):
        cb = CircuitBreaker(name="aeat_service", failure_threshold=2, recovery_timeout_seconds=60)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing_func)
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(failing_func)
        assert "aeat_service" in str(exc_info.value)


class TestCircuitBreakerHalfOpen:
    """RQ-012-03/05: Transición OPEN → HALF_OPEN → CLOSED o OPEN."""

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(name="test_half_open", failure_threshold=2, recovery_timeout_seconds=0.1)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        time.sleep(0.15)  # Esperar timeout
        # Al siguiente intento de llamada, debe pasar a HALF_OPEN y dejar pasar la petición
        success_func = MagicMock(return_value="recovered")
        result = cb.call(success_func)
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED

    def test_half_open_failure_returns_to_open(self):
        cb = CircuitBreaker(name="test_half_open_fail", failure_threshold=2, recovery_timeout_seconds=0.1)
        failing_func = MagicMock(side_effect=ConnectionError("timeout"))
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN
        time.sleep(0.15)
        # En HALF_OPEN, si falla → vuelve a OPEN
        with pytest.raises(ConnectionError):
            cb.call(failing_func)
        assert cb.state == CircuitBreakerState.OPEN


class TestCircuitBreakerDecorator:
    """RQ-012-06: El decorador @circuit_breaker debe funcionar transparentemente."""

    def test_decorator_passes_through_successful_call(self):
        @circuit_breaker(name="decorator_test", failure_threshold=3, recovery_timeout_seconds=30)
        def my_service_call(x, y):
            return x + y

        result = my_service_call(2, 3)
        assert result == 5

    def test_decorator_propagates_exception(self):
        @circuit_breaker(name="decorator_fail_test", failure_threshold=3, recovery_timeout_seconds=30)
        def my_failing_call():
            raise ConnectionError("network error")

        with pytest.raises(ConnectionError):
            my_failing_call()

    def test_decorator_opens_after_threshold(self):
        @circuit_breaker(name="decorator_open_test", failure_threshold=2, recovery_timeout_seconds=30)
        def my_failing_call():
            raise ConnectionError("network error")

        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                my_failing_call()
        with pytest.raises(CircuitBreakerOpenError):
            my_failing_call()

    def test_decorator_preserves_function_name(self):
        @circuit_breaker(name="meta_test", failure_threshold=3, recovery_timeout_seconds=30)
        def service_with_name():
            return "ok"

        assert service_with_name.__name__ == "service_with_name"
