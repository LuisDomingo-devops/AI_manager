# Implementation Tasks: Domain Error & UX Contract

**Feature**: `016-domain-error-contract`

## Phase 1: Setup
**Purpose**: No new foundational setup is required as the project structure already exists.

## Phase 2: Foundational (Blocking Prerequisites)
**Purpose**: Prerrequisitos de configuración. (Ninguno para esta feature).

---

## Phase 3: User Story 1 - Shielding Users from Technical Errors (Priority: P1)
**Goal**: Prevent technical exceptions like `ValidationError` from reaching the user prompt by returning a structured `DomainErrorContract`.

**Independent Test**: Simulate a parsing failure and verify the response asks a conversational question instead of showing raw exception details.

### Tests for User Story 1 (TDD - MUST FAIL INITIALLY)
> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T001 [P] [US1] Create unit test in `tests/backend/unit/test_domain_error_contract.py` for parsing `ValidationError` into the `DomainErrorContract` structure.
- [x] T002 [P] [US1] Create integration test in `tests/backend/integration/test_domain_error_ux.py` asserting technical errors (like Pydantic exceptions) do not leak into the user's response.

### Implementation for User Story 1

- [x] T003 [P] [US1] Create `DomainErrorContract` model in `app/domain/schemas.py` with fields `status`, `affected_fields`, `extracted_values`, `missing_values`, `reason_code`, and `technical_details` (which must be excluded from LLM serialization).
- [x] T004 [US1] Implement a tool execution wrapper or `ErrorManager` in `app/domain/services/error_manager.py` (or within the base tool executor) to catch exceptions, extract Pydantic validation errors (if applicable), and return a `DomainErrorContract`.
- [x] T005 [US1] Implement backend logging of `technical_details` inside the error manager in `app/domain/services/error_manager.py` before returning the contract, fulfilling FR-004.

**Checkpoint**: At this point, tools should safely return `DomainErrorContract` without crashing, and stack traces should only appear in logs.

---

## Phase 4: User Story 2 - Workflow Pausing on Validation (Priority: P1)
**Goal**: Synchronously pause workflows when `needs_user_validation` is emitted, asking the user for clarification without continuing blindly.

**Independent Test**: Supply a batch of files where the first fails validation, and verify the workflow pauses.

### Tests for User Story 2 (TDD - MUST FAIL INITIALLY)

- [x] T006 [P] [US2] Create unit test in `tests/backend/unit/test_planner_orchestrator.py` to ensure processing a `DomainErrorContract` with `needs_user_validation` yields a clarification/confirmation `LLMDecisionEnvelope`.
- [x] T007 [P] [US2] Create integration test in `tests/backend/integration/test_domain_error_ux.py` asserting workflow pausing on validation errors.

### Implementation for User Story 2

- [x] T008 [US2] Update `app/domain/services/planner_orchestrator.py` to intercept `DomainErrorContract` responses. If `status == "needs_user_validation"`, return a `LLMDecisionEnvelope(type=IntentType.clarification)` and halt the tool execution loop.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: Polish & Cross-Cutting Concerns
**Purpose**: Validation, code cleanliness, and Constitution Check.

- [x] T009 [P] Run quickstart validation scenarios defined in `quickstart.md` (`uv run pytest tests/backend/integration/test_domain_error_ux.py -v`).
- [x] T010 Execute all tests in the repository and verify 100% success, saving the output to a log file (Regla IV de la Constitución).

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: N/A
- **Foundational (Phase 2)**: N/A
- **User Stories (Phase 3+)**: US1 and US2 can be tested in parallel, but US2 implementation (Orchestrator) depends on US1 (Contract definition).
- **Polish (Final Phase)**: Depends on all user stories being complete.

### Parallel Example: User Story 1
```bash
# Launch tests for US1 in parallel
Task: "T001 Contract/Unit test in test_domain_error_contract.py"
Task: "T002 Integration test in test_domain_error_ux.py"
```

## Implementation Strategy

### Incremental Delivery
1. Start with US1: Define the contract and wrap the tool executions. This handles the error shielding.
2. Continue with US2: Make the orchestrator aware of the new contract and pause correctly.
3. Validate through Polish phase tests.
