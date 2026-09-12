# Feature Tasks: Consolidación Arquitectura y Conformidad VeriFactu (AEAT)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 [P] Ensure target directories exist (`app/domain/services`, `tests/backend/integration`, `tests/backend/unit`, `tests/backend/qa`)
- [x] T002 [P] Verify/install required dependencies (`lxml`, `signxml`, `httpx`, `pytest`) en el entorno del proyecto

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Implementar la migración de base de datos canónica en `migrations/versions/012_verifactu_sif_canonical.py` (Tablas para RegistroFacturacion, RespuestaAEAT y ConfiguracionVeriFactu)
- [x] T004 Aplicar la migración de esquema en la base de datos de desarrollo/test

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Verificación de Conformidad con AEAT (Priority: P1)

**Goal**: Generar, firmar y enviar XML a la AEAT, recibiendo validación.

**Independent Test**: Test unitario de esquemas y endpoints.

### Tests for User Story 1 (TDD)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T005 [P] [US1] Create unit tests for XML serialization and endpoint logic in `tests/backend/unit/test_verifactu_schema_and_endpoint_unit.py`

### Implementation for User Story 1

- [x] T006 [US1] Implement XML serialization and XMLDSig chaining logic directly in `app/domain/services/verifactu_service.py` (depends on DB models from T003)
- [x] T007 [US1] Implement AEAT HTTP/SOAP connection and validation handling in `app/domain/services/verifactu_service.py`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Ejecución de Suite de Tests de Integración (Priority: P2)

**Goal**: Ejecutar tests de integración end-to-end con la AEAT sin afectar producción, generando logs.

**Independent Test**: Ejecución completa de la suite de tests de integración del backend.

### Tests for User Story 2 (TDD)

- [x] T008 [P] [US2] Create integration test for standard invoice flows in `tests/backend/integration/test_verifactu.py`
- [x] T009 [P] [US2] Create integration test for real SOAP connection in `tests/backend/integration/test_verifactu_real_soap.py`
- [x] T010 [P] [US2] Create tests for invoice annulment in `tests/backend/integration/test_verifactu_anulacion.py`
- [x] T011 [P] [US2] Create tests for ledger integrity in `tests/backend/integration/test_verifactu_integrity.py`
- [x] T012 [P] [US2] Create migration integration tests in `tests/backend/integration/test_verifactu_sif_migration_integration.py`

### Implementation for User Story 2

- [x] T013 [US2] Configurar la recolección de logs obligatoria (Constitución) en el framework de `pytest` para la suite de integración backend

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T014 [P] Ejecutar la suite avanzada de QA en `tests/backend/qa/` (crear scripts si no existen)
- [x] T015 [P] Actualizar la documentación y `quickstart.md` para reflejar la nueva arquitectura hexagonal

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 -> P2)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on User Story 1 completion.

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001 and T002 en Setup
- Todos los tests de la Fase 4 (T008 a T012) pueden desarrollarse y ejecutarse en paralelo.

---

## Parallel Example: User Story 2

```bash
# Launch multiple integration tests for User Story 2 together:
Task: "Create integration test for standard invoice flows in tests/backend/integration/test_verifactu.py"
Task: "Create integration test for real SOAP connection in tests/backend/integration/test_verifactu_real_soap.py"
Task: "Create tests for invoice annulment in tests/backend/integration/test_verifactu_anulacion.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently

### Incremental Delivery

1. Complete Setup + Foundational -> Foundation ready
2. Add User Story 1 -> Test independently -> Deploy/Demo (MVP!)
3. Add User Story 2 -> Test independently -> Deploy/Demo
