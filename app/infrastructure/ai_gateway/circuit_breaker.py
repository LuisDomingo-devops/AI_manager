"""Mecanismo de Circuit Breaker para la Pasarela de IA de Escritorio.

Previene bloqueos en la interfaz cuando el servicio externo no está disponible.
"""

import time
import logging
from enum import Enum
from typing import Optional

logger = logging.getLogger("ai_circuit_breaker")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Controlador de estado de salud del circuito de pasarela de IA."""

    def __init__(self, failure_threshold: int = 3, recovery_time_seconds: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_time_seconds = recovery_time_seconds
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> str:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.time() - self._last_failure_time >= self.recovery_time_seconds:
                self._state = CircuitState.HALF_OPEN
        return self._state.value

    def record_success(self) -> None:
        """Registra un éxito y restablece el contador de fallos."""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Registra un fallo e incrementa el contador. Si supera el umbral, abre el circuito."""
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker abierto tras {self._failure_count} fallos consecutivos."
            )

    def can_execute(self) -> bool:
        """Retorna True si la petición puede proceder o False si el circuito está abierto."""
        return self.state != CircuitState.OPEN.value
