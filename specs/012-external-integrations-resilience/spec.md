# Spec 012 — External Integrations Resilience

## Objetivo

Implementar un mecanismo de resiliencia (Circuit Breaker) para las llamadas a servicios externos
(AEAT, Stripe, TGSS) que evite cascadas de error cuando un proveedor externo falla,
permitiendo recuperación automática.

## Contexto

El sistema realiza llamadas a pasarelas externas críticas sin ningún mecanismo de protección
ante fallos en cascada. Si AEAT o Stripe no responden, las peticiones bloquean recursos
indefinidamente y pueden colapsar el sistema.

## Requerimientos

### RQ-012-01 — Circuit Breaker con 3 estados
El sistema debe implementar un Circuit Breaker con los estados:
- `CLOSED`: Comportamiento normal, peticiones pasan.
- `OPEN`: Bloqueado, retorna error rápido sin llamada real a la red.
- `HALF_OPEN`: Período de prueba: un intento pasa, si falla vuelve a OPEN, si éxito → CLOSED.

### RQ-012-02 — Transición CLOSED → OPEN
Tras `failure_threshold` fallos consecutivos en estado CLOSED, el CB transiciona a OPEN.

### RQ-012-03 — Transición OPEN → HALF_OPEN
Tras `recovery_timeout_seconds` en estado OPEN, el CB pasa a HALF_OPEN automáticamente.

### RQ-012-04 — Retorno rápido en estado OPEN
En estado OPEN, la llamada debe retornar `CircuitBreakerOpenError` inmediatamente sin intentar
la conexión de red.

### RQ-012-05 — Recuperación en HALF_OPEN
En HALF_OPEN: primera llamada exitosa → CLOSED; primera llamada fallida → OPEN.

### RQ-012-06 — Decorador de uso simple
Debe existir un decorador `@circuit_breaker(name="...")` para aplicar el CB a cualquier función
de adaptador sin cambiar la lógica de negocio.

## Constraints

- NO inventar endpoints AEAT/Stripe reales: los tests usan mocks controlados.
- El CB es un componente de infraestructura independiente de la lógica de dominio.
- Las migraciones de BD NO se modifican.
- Los mocks deben aislar la red real (no hacer llamadas HTTP en tests).
