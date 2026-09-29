# Implementation Tasks: End-to-End Interaction Test Suite

**Feature**: `017-e2e-interaction-test-suite`

> **IMPORTANTE**: Esta spec genera ÚNICAMENTE tests. No se modifica ningún código de producción.
> Toda la implementación reside en `tests/backend/integration/test_e2e_interaction_suite.py`.

---

## Phase 1: Setup
**Purpose**: Verificar que la estructura de tests existe y crear el archivo base con las fixtures compartidas.

- [x] T001 Crear el archivo de test `tests/backend/integration/test_e2e_interaction_suite.py` con las fixtures compartidas: `e2e_memory` (DummyMemory local) y `mock_llm` (AsyncMock).

---

## Phase 2: Foundational (Blocking Prerequisites)
**Purpose**: No hay prerrequisitos de código de producción. Los prerrequisitos son que los mocks de los componentes sean verificables.

- [x] T002 Verificar en `tests/backend/integration/test_e2e_interaction_suite.py` que `PlannerOrchestrator` puede instanciarse con los mocks `mock_llm`, `e2e_memory` y `mock_vector` sin errores de importación.

---

## Phase 3: User Story 1 - Conversational Boundaries (Priority: P1)
**Goal**: Los mensajes conversacionales nunca activan tools ni se interpretan como confirmaciones de workflow.

**Independent Test**: `uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc1 or sc2 or sc3" -v`

### Tests for User Story 1 (TDD — MUST FAIL INITIALLY)

- [x] T003 [P] [US1] Implementar `test_sc1_hola_es_conversacional`
- [x] T004 [P] [US1] Implementar `test_sc2_no_saludas_no_confirmation`
- [x] T005 [P] [US1] Implementar `test_sc3_tiempo_bilbao_no_protocol_error`

**Checkpoint**: Los 3 tests pasan. Los escenarios SC1, SC2, SC3 están cubiertos.

---

## Phase 4: User Story 2 - Contextual and Domain Stickiness (Priority: P1)
**Goal**: Las consultas contables se mantienen en el orquestador sin desviarse a MarcosAgent.

**Independent Test**: `uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc4 or sc5 or sc6" -v`

### Tests for User Story 2 (TDD — MUST FAIL INITIALLY)

- [x] T006 [P] [US2] Implementar `test_sc4_cuanto_iva_no_marcos`
- [x] T007 [P] [US2] Implementar `test_sc5_correccion_iva_domain_stickiness`
- [x] T008 [P] [US2] Implementar `test_sc6_inventando_iva_no_marcos`

**Checkpoint**: Los 3 tests pasan. Los escenarios SC4, SC5, SC6 están cubiertos.

---

## Phase 5: User Story 3 - Robust Document Extraction (Priority: P1)
**Goal**: Las facturas problemáticas pausan el workflow sin filtrar errores técnicos. Las facturas limpias se extraen con precisión.

**Independent Test**: `uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc7 or sc8" -v`

### Tests for User Story 3 (TDD — MUST FAIL INITIALLY)

- [x] T009 [US3] Implementar `test_sc7_factura_ilegible_domain_error_contract`
- [x] T010 [P] [US3] Implementar `test_sc8_extraccion_exacta_factura`

**Checkpoint**: Los 2 tests pasan. Los escenarios SC7, SC8 están cubiertos.

---

## Phase 6: User Story 4 - Explicit Legal Queries (Priority: P1)
**Goal**: Las consultas legales explícitas se enrutan a MarcosAgent con exactamente un disclaimer.

**Independent Test**: `uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -k "sc9" -v`

### Tests for User Story 4 (TDD — MUST FAIL INITIALLY)

- [x] T011 [US4] Implementar `test_sc9_consulta_legal_marcos_con_disclaimer`

**Checkpoint**: El test pasa. El escenario SC9 está cubierto.

---

## Phase 7: Polish & Cross-Cutting Concerns
**Purpose**: Validación completa y log de ejecución (Regla IV de la Constitución).

- [x] T012 [P] Ejecutar todos los escenarios E2E juntos y verificar que los 9 pasan: `uv run pytest tests/backend/integration/test_e2e_interaction_suite.py -v`.
- [x] T013 Ejecutar la suite completa del repositorio (`uv run pytest`) y guardar el log en `tests_execution_017.log`.

---

## Dependencies & Execution Order

### Dependencias entre fases
- **Phase 1** (Setup): Independiente — puede comenzar de inmediato.
- **Phase 2** (Foundational): Depende de Phase 1.
- **Phases 3-6** (User Stories): Dependen de Phase 2; las 4 fases son **paralelas** entre sí al compartir el mismo archivo.
- **Phase 7** (Polish): Depende de que los 9 tests pasen.

### Oportunidades de paralelismo

Los tests T003-T011 escriben en el **mismo archivo** `test_e2e_interaction_suite.py`, por lo que se deben implementar **secuencialmente** aunque los tests individuales son independientes en ejecución.

## Implementation Strategy

### Entrega incremental
1. T001-T002: Crear archivo con fixtures. Verificar importaciones.
2. T003-T005: US1 (3 escenarios conversacionales).
3. T006-T008: US2 (3 escenarios de domain stickiness).
4. T009-T010: US3 (2 escenarios de extracción de documentos).
5. T011: US4 (1 escenario legal explícito).
6. T012-T013: Validación final y log.
