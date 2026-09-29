"""
Tests de integración para resiliencia de servicios externos.
TDD RED phase: verifican que el CB protege las llamadas a adaptadores externos.

Servicios bajo prueba (mockeados): AEAT, Stripe, TGSS
"""
import pytest
from unittest.mock import MagicMock, patch

from app.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitBreakerState,
)


class TestExternalServiceProtectedByCircuitBreaker:
    """El CB protege llamadas a servicios externos sin intentar conexión real."""

    def test_aeat_service_open_circuit_returns_fast_error(self):
        """Cuando el CB de AEAT está OPEN, la llamada retorna inmediatamente."""
        cb = CircuitBreaker(name="aeat_verifactu", failure_threshold=3, recovery_timeout_seconds=60)
        mock_aeat_call = MagicMock(side_effect=ConnectionError("AEAT no disponible"))

        # Agotar threshold
        for _ in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(mock_aeat_call)

        # Reiniciar contador de llamadas al mock
        mock_aeat_call.reset_mock()

        # El CB debe bloquear SIN llamar a AEAT
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(mock_aeat_call)

        mock_aeat_call.assert_not_called()

    def test_stripe_service_open_circuit_returns_fast_error(self):
        """Cuando el CB de Stripe está OPEN, la llamada retorna inmediatamente."""
        cb = CircuitBreaker(name="stripe_payment", failure_threshold=3, recovery_timeout_seconds=60)
        mock_stripe_call = MagicMock(side_effect=ConnectionError("Stripe unavailable"))

        for _ in range(3):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb.call(mock_stripe_call)

        mock_stripe_call.reset_mock()

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(mock_stripe_call)

        mock_stripe_call.assert_not_called()

    def test_tgss_service_open_circuit_returns_fast_error(self):
        """Cuando el CB de TGSS está OPEN, la llamada retorna inmediatamente."""
        cb = CircuitBreaker(name="tgss_social_security", failure_threshold=3, recovery_timeout_seconds=60)
        mock_tgss_call = MagicMock(side_effect=TimeoutError("TGSS timeout"))

        for _ in range(3):
            with pytest.raises((TimeoutError, CircuitBreakerOpenError)):
                cb.call(mock_tgss_call)

        mock_tgss_call.reset_mock()

        with pytest.raises(CircuitBreakerOpenError):
            cb.call(mock_tgss_call)

        mock_tgss_call.assert_not_called()


class TestMultipleIndependentCircuitBreakers:
    """Cada servicio externo debe tener su propio CB independiente."""

    def test_aeat_failure_does_not_affect_stripe_circuit(self):
        """El fallo de AEAT no debe abrir el CB de Stripe."""
        cb_aeat = CircuitBreaker(name="aeat_ind", failure_threshold=2, recovery_timeout_seconds=60)
        cb_stripe = CircuitBreaker(name="stripe_ind", failure_threshold=2, recovery_timeout_seconds=60)

        mock_aeat = MagicMock(side_effect=ConnectionError("AEAT down"))

        # Abrir AEAT CB
        for _ in range(2):
            with pytest.raises((ConnectionError, CircuitBreakerOpenError)):
                cb_aeat.call(mock_aeat)

        assert cb_aeat.state == CircuitBreakerState.OPEN

        # Stripe CB sigue CLOSED
        assert cb_stripe.state == CircuitBreakerState.CLOSED

        # Stripe puede seguir recibiendo llamadas
        mock_stripe = MagicMock(return_value={"status": "ok"})
        result = cb_stripe.call(mock_stripe)
        assert result == {"status": "ok"}

    def test_independent_failure_counts(self):
        """Los contadores de fallos son independientes entre instancias."""
        cb1 = CircuitBreaker(name="svc_a", failure_threshold=3, recovery_timeout_seconds=60)
        cb2 = CircuitBreaker(name="svc_b", failure_threshold=3, recovery_timeout_seconds=60)

        failing = MagicMock(side_effect=Exception("error"))

        for _ in range(2):
            with pytest.raises(Exception):
                cb1.call(failing)

        assert cb1.failure_count == 2
        assert cb2.failure_count == 0


class TestCircuitBreakerErrorStructure:
    """CircuitBreakerOpenError debe tener información estructurada."""

    def test_error_contains_service_name(self):
        cb = CircuitBreaker(name="aeat_structured", failure_threshold=2, recovery_timeout_seconds=60)
        failing = MagicMock(side_effect=Exception("error"))

        for _ in range(2):
            with pytest.raises((Exception, CircuitBreakerOpenError)):
                cb.call(failing)

        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(failing)

        error_msg = str(exc_info.value)
        assert "aeat_structured" in error_msg

    def test_error_is_an_exception(self):
        assert issubclass(CircuitBreakerOpenError, Exception)
