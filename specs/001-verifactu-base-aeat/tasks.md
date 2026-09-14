# Tasks: Consolidación Arquitectura y Conformidad VeriFactu (AEAT)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Initialize environment and dependencies (pytest, lxml, httpx)
- [ ] T002 Configure linting and formatting tools

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [ ] T003 Setup test framework and ephemeral DB fixture patterns
- [ ] T004 Define common Error Handling and Logging infrastructure
- [ ] T005 [P] Consolidate `ConfiguracionVeriFactu` and base domain models

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Verificación de Conformidad con AEAT (Priority: P1)

**Goal**: Asegurar que las facturas emitidas cumplen con todos los requisitos del formato y protocolo de envío de la AEAT.

**Independent Test**: Envío de facturas de prueba al entorno de validación/sandbox de la AEAT (HTTP 200).

### Implementation for User Story 1

- [ ] T006 [US1] Create XML Serialization module for VeriFactu using `lxml`
- [ ] T007 [US1] Implement XMLDSig signing or secure hash chaining for VeriFactu
- [ ] T008 [US1] Implement `verifactu_service.py` HTTP client to communicate with AEAT sandbox
- [ ] T009 [US1] Create unit tests for XML serialization and signing
- [ ] T010 [US1] Add response parsing and error handling for AEAT responses

**Checkpoint**: User Story 1 functional

---

## Phase 4: User Story 2 - Ejecución de Suite de Tests de Integración (Priority: P2)

**Goal**: Ejecutar una suite de tests de integración completa para el módulo VeriFactu.

**Independent Test**: Ejecución automatizada de pytest evidenciando resultados exitosos.

### Implementation for User Story 2

- [ ] T011 [US2] Implement test fixture mock for AEAT responses
- [ ] T012 [P] [US2] Create integration test `test_verifactu.py` for full invoice generation and sending flow
- [ ] T013 [P] [US2] Create integration test `test_verifactu_anulacion.py` for cancellation flow
- [ ] T014 [US2] Set up logging output for the test suite execution

**Checkpoint**: User Story 2 functional

---

## Phase 5: User Story 3 - Resolución de Deuda Técnica y Seguridad (Priority: P1)

**Goal**: Eliminar vulnerabilidades y asegurar el correcto funcionamiento en producción.

**Independent Test**: Auditoría de código, tests CI y pruebas de inyección de fallos.

### Implementation for User Story 3

- [x] T015 [US3] Refactor `app/config.py` to securely manage API keys without plain text disk persistence
- [x] T016 [US3] Consolidate authentication in `api/auth_router.py` to use only JWT, removing `verify_api_key`
- [x] T017 [US3] Modify `verifactu_service.py` to strictly disable `offline_simulated` fallback when running in production
- [x] T018 [US3] Remove `except Exception: pass` from `domain/services/bank_service.py` and implement proper error logging
- [x] T019 [US3] Remove `except Exception: pass` from `domain/services/mail_tools.py` and implement proper error logging
- [ ] T020 [US3] Refactor existing tests to remove shared disk state and utilize ephemeral fixtures

**Checkpoint**: User Story 3 functional

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T021 Code cleanup and refactoring
- [ ] T022 Update quickstart.md validation guide
- [ ] T023 Final security audit of modified files

---

## Dependencies & Execution Order

- **Phase 1 & 2**: Setup and Foundational tasks must be completed first.
- **Phase 3 (US1) & Phase 5 (US3)**: Are P1 and must be addressed early. Resolving technical debt (US3) in authentication and error handling might be best done in parallel or prior to heavy integration tests.
- **Phase 4 (US2)**: Integration test suite improvements build upon US1 and US3 refactors.

## Implementation Strategy

1. Resolve technical debt blocks (US3) and ensure basic foundational setup.
2. Develop the core AEAT conformity logic (US1).
3. Expand integration tests (US2) against the newly secured and stable base.
