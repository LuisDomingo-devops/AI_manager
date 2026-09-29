# Plan de Implementación: 008-routing-integrity

## 1. Arquitectura y Enfoque

El objetivo es corregir el fallo de enrutamiento detectado en la Sección 11 del Discovery Contract:
- `"word" in msg_lower` provoca que solicitudes con `"password"` se interpreten erróneamente como peticiones ofimáticas de Microsoft Word, secuestrando la intención del usuario.
- Sustituiremos la búsqueda ingenua de subcadenas en `SpecializedAgentRouter` por expresiones regulares con fronteras de palabra (`\bword\b`), al igual que ya se hace para `ExcelAgent`.
- Se añadirán pruebas exhaustivas de límites léxicos.

## 2. Fases de Ejecución

- **Fase 1 (Setup)**:
  - Crear directorio para logs en `tests/logs/spec008/`.

- **Fase 2 (TDD Red)**:
  - Crear test unitario `tests/backend/unit/test_routing_word_agent_boundaries.py` que demuestre que actualmente `"genera un password"` es erróneamente enrutado a WordAgent.
  - Crear test de integración `tests/backend/integration/test_orchestrator_routing_integrity_integration.py` evaluando las fronteras del router.
  - Ejecutar tests y guardar evidencia de fallo RED en `tests/logs/spec008/us1_red.log`.

- **Fase 3 (TDD Green)**:
  - Modificar `app/domain/planner_orchestrator.py` en `SpecializedAgentRouter.route_if_applicable()` para usar límites de palabra `\bword\b`, `\bdocx\b`, etc.
  - Ejecutar tests unitario e integración para verificar pase a verde y registrar en `tests/logs/spec008/us2_green.log`.

- **Fase 4 (QA y Resiliencia)**:
  - Crear `tests/backend/qa/test_routing_integrity_qa_suite.py` con combinatoria de casos límite (`sword`, `password`, `forward`, `word docx`).
  - Ejecutar suite de QA y guardar log en `tests/logs/spec008/us3_green.log`.

- **Fase 5 (Validación Completa y Certificación)**:
  - Ejecutar suite completa de backend y certificar cero regresiones.
  - Consolidar commit formal en Git.
