# Tareas de Implementación: 008-routing-integrity

## Phase 1: Setup y Preparación de Entorno

- [x] T001 Crear directorio para logs de ejecución de pruebas en `tests/logs/spec008/`.

---

## Phase 2: User Story 1 (P1) — TDD RED (Fallo Verificado por Falsos Positivos de "word" en "password")

**Meta**: Demostrar con evidencia reproducible que consultas con `"password"` son capturadas erróneamente por WordAgent debido a `"word" in msg_lower`.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_routing_word_agent_boundaries.py` que compruebe que `"genera un password"` no debe ser clasificado como consulta de Word ni enrutado a WordAgent.
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_orchestrator_routing_integrity_integration.py` que verifique que `SpecializedAgentRouter.route_if_applicable()` no delega en WordAgent ante mensajes como `"genera una password segura"` o `"password reset"`.
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log de evidencia en `tests/logs/spec008/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Reemplazar subcadenas permisivas por expresiones regulares con fronteras de palabra (`\b`) en `SpecializedAgentRouter`.

### Implementación (Fase GREEN)
- [x] T005 [US2] En `app/domain/planner_orchestrator.py`, refactorizar `SpecializedAgentRouter.route_if_applicable()` para usar `re.search(r"\bword\b", msg_lower)` y límites en palabras clave ofimáticas.
- [x] T006 [US2] Ejecutar `test_routing_word_agent_boundaries.py` y `test_orchestrator_routing_integrity_integration.py`, registrando pase a verde en `tests/logs/spec008/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — QA y Resiliencia de Enrutamiento

**Meta**: Certificar la discriminación precisa ante homónimos accidentales y combinaciones léxicas.

### Tests QA
- [x] T007 [P] [US3] Crear suite de QA en `tests/backend/qa/test_routing_integrity_qa_suite.py` con una matriz exhaustiva de palabras clave (password, foreword, sword, crossword vs Microsoft Word, documento docx).
- [x] T008 [US3] Ejecutar `test_routing_integrity_qa_suite.py` y guardar log en `tests/logs/spec008/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T009 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T010 Consolidar commit formal de entrega de la Spec 008.
