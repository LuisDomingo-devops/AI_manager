# Plan 012 — External Integrations Resilience

## Arquitectura

```
app/infrastructure/resilience/
├── __init__.py
└── circuit_breaker.py          ← Implementación del CB
```

## Decisiones de diseño

1. **Thread-safe**: El CB usa `threading.Lock` para proteger los contadores.
2. **Configurable por instancia**: `failure_threshold` y `recovery_timeout_seconds` por CB.
3. **Sin dependencias externas**: Solo librería estándar de Python.
4. **Decorador funcional**: `@circuit_breaker(name)` compatible con funciones sync y async.

## Interfaz pública

```python
class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is in OPEN state."""

class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5,
                 recovery_timeout_seconds: float = 60.0): ...
    def call(self, func: Callable, *args, **kwargs) -> Any: ...

def circuit_breaker(name: str, **kwargs) -> Callable: ...
```

## Tests requeridos

| Tipo | Archivo | Descripción |
|------|---------|-------------|
| Unit | `test_external_circuit_breaker.py` | Transiciones CLOSED→OPEN→HALF_OPEN→CLOSED |
| Integration | `test_external_services_resilience_integration.py` | CB protege llamadas reales (mockeadas) |
| QA | `test_external_integrations_resilience_qa_suite.py` | Ráfagas de fallos y recuperación |
