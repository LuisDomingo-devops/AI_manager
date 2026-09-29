"""
Circuit Breaker para proteger llamadas a servicios externos.

Implementa el patrón Circuit Breaker con 3 estados:
- CLOSED: Comportamiento normal, peticiones pasan.
- OPEN: Bloqueado, retorna error rápido sin llamada real a la red.
- HALF_OPEN: Período de prueba: primer intento pasa.

Ref: RQ-012-01 a RQ-012-06
"""
import threading
import time
import functools
import logging
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenError(Exception):
    """
    Excepción lanzada cuando el Circuit Breaker está en estado OPEN.
    La llamada al servicio externo se rechaza inmediatamente sin intentar
    ninguna conexión de red.
    """

    def __init__(self, service_name: str):
        self.service_name = service_name
        super().__init__(
            f"Circuit breaker OPEN para el servicio '{service_name}'. "
            f"Las llamadas están temporalmente bloqueadas hasta que el servicio se recupere."
        )


class CircuitBreaker:
    """
    Circuit Breaker thread-safe para proteger llamadas a servicios externos.

    Args:
        name: Identificador del servicio (ej. "aeat_verifactu", "stripe_payment").
        failure_threshold: Número de fallos consecutivos para pasar a OPEN.
        recovery_timeout_seconds: Segundos en OPEN antes de transicionar a HALF_OPEN.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def _check_and_transition_to_half_open(self) -> bool:
        """
        Comprueba si el timeout ha expirado y transiciona OPEN → HALF_OPEN.
        Debe llamarse dentro del lock.
        Retorna True si se ha transitado a HALF_OPEN.
        """
        if (
            self._state == CircuitBreakerState.OPEN
            and self._opened_at is not None
            and (time.monotonic() - self._opened_at) >= self.recovery_timeout_seconds
        ):
            self._state = CircuitBreakerState.HALF_OPEN
            logger.info(
                "Circuit breaker '%s': OPEN → HALF_OPEN (timeout de %.1fs expirado)",
                self.name,
                self.recovery_timeout_seconds,
            )
            return True
        return False

    def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """
        Ejecuta `func(*args, **kwargs)` protegida por el circuit breaker.

        - En CLOSED: ejecuta normalmente; cuenta fallos; en éxito resetea contador.
        - En OPEN: lanza CircuitBreakerOpenError inmediatamente sin llamar a func.
        - En HALF_OPEN: deja pasar una llamada de prueba:
            - Éxito → CLOSED
            - Fallo → OPEN (reinicia timer)
        """
        with self._lock:
            self._check_and_transition_to_half_open()
            current_state = self._state

            if current_state == CircuitBreakerState.OPEN:
                raise CircuitBreakerOpenError(self.name)

        # Ejecutar fuera del lock para no bloquear otros hilos
        try:
            result = func(*args, **kwargs)
        except Exception as exc:
            with self._lock:
                self._on_failure()
            raise

        with self._lock:
            self._on_success()

        return result

    def _on_success(self) -> None:
        """Maneja un resultado exitoso. Debe llamarse dentro del lock."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            logger.info(
                "Circuit breaker '%s': HALF_OPEN → CLOSED (recuperación exitosa)",
                self.name,
            )
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._opened_at = None
        elif self._state == CircuitBreakerState.CLOSED:
            # Resetear contador de fallos en éxito durante CLOSED
            self._failure_count = 0

    def _on_failure(self) -> None:
        """Maneja un fallo. Debe llamarse dentro del lock."""
        if self._state == CircuitBreakerState.HALF_OPEN:
            # Fallo en prueba → vuelve a OPEN
            self._state = CircuitBreakerState.OPEN
            self._opened_at = time.monotonic()
            logger.warning(
                "Circuit breaker '%s': HALF_OPEN → OPEN (fallo en prueba de recuperación)",
                self.name,
            )
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                self._opened_at = time.monotonic()
                logger.warning(
                    "Circuit breaker '%s': CLOSED → OPEN (alcanzado threshold de %d fallos)",
                    self.name,
                    self.failure_threshold,
                )


def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout_seconds: float = 60.0,
) -> Callable:
    """
    Decorador que envuelve una función con un Circuit Breaker.

    Cada función decorada con el mismo `name` comparte la misma instancia de CB.
    Si se usa el mismo `name` en distintas funciones, comparten el estado del CB.

    Uso:
        @circuit_breaker(name="aeat_verifactu", failure_threshold=3)
        def enviar_a_aeat(factura: dict) -> dict:
            ...

    Args:
        name: Nombre identificador del servicio externo.
        failure_threshold: Fallos consecutivos antes de OPEN.
        recovery_timeout_seconds: Segundos en OPEN antes de HALF_OPEN.
    """
    _instance = CircuitBreaker(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout_seconds,
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return _instance.call(func, *args, **kwargs)

        return wrapper

    return decorator
