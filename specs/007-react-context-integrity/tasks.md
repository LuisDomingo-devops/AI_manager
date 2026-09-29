# Tareas de Implementación: 007-react-context-integrity

## Phase 1: Setup y Preparación de Entorno

- [x] T001 Crear directorio para logs de ejecución de pruebas en `tests/logs/spec007/`.

---

## Phase 2: User Story 1 (P1) — TDD RED (Fallo Verificado por Duplicación de Hechos)

**Meta**: Demostrar con evidencia reproducible que `VectorMemory.add_fact` genera UUIDs aleatorios y duplica entradas al registrar el mismo hecho múltiples veces.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_vector_memory_fact_deduplication.py` que compruebe que al insertar dos veces el mismo hecho, se debe obtener el mismo ID determinista y un único documento en la colección.
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_react_context_fact_deduplication_integration.py` que ejecute `build_context` con el mismo mensaje en múltiples iteraciones y compruebe que no se generan duplicados lógicos en la memoria semántica (`same fact + multiple iterations = one logical fact`).
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log de evidencia en `tests/logs/spec007/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Implementar identidad determinista del hecho y deduplicación con upsert en `VectorMemory`.

### Implementación (Fase GREEN)
- [x] T005 [US2] Implementar cálculo de ID determinista basado en el contenido normalizado y tenant en `app/infrastructure/database/memory/vector_memory.py`.
- [x] T006 [US2] Reemplazar `collection.add(...)` con `collection.upsert(...)` (o comprobación/actualización idempotente) en `VectorMemory.add_fact()`.
- [x] T007 [US2] Ejecutar `test_vector_memory_fact_deduplication.py` y `test_react_context_fact_deduplication_integration.py`, registrando pase a verde en `tests/logs/spec007/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — QA y Resiliencia de Contexto

**Meta**: Certificar la preservación de hechos únicos, normalización de espacios/mayúsculas y consultas semánticas.

### Tests QA
- [x] T008 [P] [US3] Crear suite de QA en `tests/backend/qa/test_react_context_integrity_qa_suite.py` comprobando normalización, coexistencia de hechos diferentes y deduplicación estricta entre sesiones.
- [x] T009 [US3] Ejecutar `test_react_context_integrity_qa_suite.py` y guardar log en `tests/logs/spec007/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T010 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T011 Consolidar commit formal de entrega de la Spec 007.
