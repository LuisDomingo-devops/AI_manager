# Feature Specification: End-to-End Interaction Test Suite

**Feature Branch**: `017-e2e-interaction-test-suite`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Crear una suite de pruebas end-to-end para validar la interacción de Alfonso después de las correcciones anteriores. Los escenarios deben reproducir el diagnóstico original..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversational Boundaries (Priority: P1)

Users want conversational input to be handled natively without attempting to trigger background scripts or operational tools.

**Acceptance Scenarios**:
1. **SCENARIO 1**: **Given** the user inputs "hola", **Then** the response must be conversational, tool calls must be zero, and specifically `list_directory` and `parse_invoice` must not execute.
2. **SCENARIO 2**: **Given** the user inputs "no saludas?", **Then** the response must be conversational, tool calls must be zero, and it must not be interpreted as an implicit confirmation for a pending workflow.
3. **SCENARIO 3**: **Given** the user inputs "tiempo en Bilbao", **Then** the system classifies it as informational intent, utilizing the browser/search if applicable, but MUST NOT throw a protocol error (e.g., `JSONDecodeError`) to control the fallback flow.

---

### User Story 2 - Contextual and Domain Stickiness (Priority: P1)

Users want short accounting queries and corrections to remain in the accounting domain without being falsely routed to the legal agent.

**Acceptance Scenarios**:
1. **SCENARIO 4**: **Given** the user asks "¿cuánto IVA he pagado?", **Then** the system identifies an accounting intent, keeps the query in the Orchestrator (does not route to MarcosAgent), and successfully distinguishes between "IVA soportado" and "IVA devengado" in the response.
2. **SCENARIO 5**: **Given** the user corrects the agent with "me has dicho el IVA cobrado, yo te pregunto por el pagado", **Then** the system remains in the accounting domain (no MarcosAgent) and appropriately corrects the previous interpretation.
3. **SCENARIO 6**: **Given** the user says "te estás inventando el IVA", **Then** the system maintains the accounting/contextual domain without triggering MarcosAgent unless explicit legal petition is found.

---

### User Story 3 - Robust Document Extraction (Priority: P1)

Users want accurate invoice extraction that handles errors gracefully without leaking raw technical issues.

**Acceptance Scenarios**:
1. **SCENARIO 7**: **Given** a highly problematic or illegible invoice file, **Then** the system must not show a Pydantic `ValidationError` or stack trace, must not blame the document explicitly for technical faults, must not retry `parse_invoice` five consecutive times in an infinite loop, and MUST gracefully solicit human validation for the affected fields.
2. **SCENARIO 8**: **Given** an invoice containing exactly "base 34.51", "IVA 21%", and "total 41.76", **Then** the extraction must be flawless resulting in: `iva_rate = 21`, `base = 34.51`, `iva_amount = 7.25`, and `total = 41.76`.

---

### User Story 4 - Explicit Legal Queries (Priority: P1)

Users want clear legal questions to be answered by the specialized legal agent safely.

**Acceptance Scenarios**:
1. **SCENARIO 9**: **Given** the user inputs an explicit legal question like "¿Es legal hacer esto?", **Then** the Orchestrator successfully routes to MarcosAgent, MarcosAgent provides the answer WITHOUT converting into an Orchestrator (does not ask for tools), and exactly ONE legal disclaimer is appended to the final response.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST explicitly evaluate both the textual responses and the internal side effects of the system.
- **FR-002**: For every scenario, the test suite MUST assert the number and type of tool calls (`len(tool_calls) == 0`).
- **FR-003**: The test suite MUST assert the agent selected (e.g., verifying `MarcosAgent` is only loaded for Scenario 9).
- **FR-004**: The test suite MUST track the number of executions in a single user turn to ensure infinite loops (like 5 consecutive `parse_invoice` calls) do not occur.
- **FR-005**: The test suite MUST assert the final session state and any events emitted by the `EventBus` to ensure proper pausing or continuing of workflows.
- **FR-006**: The test suite MUST assert the absence of specific error strings (e.g., `ValidationError`, `JSONDecodeError`, `traceback`) in the final output.

### Key Entities

- **E2E_Test_Runner**: A dedicated testing fixture that simulates the full lifecycle (Frontend -> API -> Orchestrator -> LLM -> Tool) to verify the side effects and final text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 9 scenarios are mapped to automated Python integration tests (`pytest`).
- **SC-002**: 100% of these 9 E2E tests pass reliably without flaky behaviour.
- **SC-003**: The assertions in the tests deeply inspect side effects, including `tool_calls`, `events_emitted`, and `selected_agent`, not just keyword matching in the final text.
