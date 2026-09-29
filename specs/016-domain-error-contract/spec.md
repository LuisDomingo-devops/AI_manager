# Feature Specification: Domain Error & UX Contract

**Feature Branch**: `016-domain-error-contract`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Implementar un contrato de errores de herramientas orientado a dominio y UX. Una excepción técnica nunca debe cruzar directamente hacia la respuesta del usuario..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Shielding Users from Technical Errors (Priority: P1)

Users should experience a natural, conversational recovery when a tool fails to parse or process data, without ever seeing raw technical details.

**Why this priority**: Directly addresses P-03 (Fuga de errores Pydantic al prompt), which severely degrades UX and exposes internal system structures.

**Independent Test**: Can be tested by forcing a parsing failure (e.g., providing corrupted invoice data) and asserting that the LLM response does not contain technical keywords while the backend logs do.

**Acceptance Scenarios**:

1. **Given** an invoice where the IVA rate cannot be extracted (validation failure), **When** the tool yields an error, **Then** the user receives a conversational prompt like "No he podido extraer correctamente el IVA. ¿Puedes confirmarme el porcentaje?", and the system logs the full `Pydantic ValidationError` internally.

---

### User Story 2 - Workflow Pausing on Validation (Priority: P1)

Users must be able to address issues synchronously without the system running away and ignoring the problem or continuing blindly.

**Why this priority**: Essential to prevent data corruption where unvalidated or assumed values are skipped and the next document is processed.

**Independent Test**: Can be tested by submitting a batch of files where the first fails validation, and verifying the second is not processed until the user answers the clarification prompt.

**Acceptance Scenarios**:

1. **Given** a workflow processing multiple files, **When** one file triggers a `needs_user_validation` status, **Then** the system pauses the workflow immediately, asks the user for the missing data, and DOES NOT process subsequent documents until authorization/clarification is received.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a domain-oriented error contract for tools. When an extraction or validation fails, the tool MUST return a structured object instead of throwing a raw exception upwards. The contract MUST include:
  - `status`: e.g., "needs_user_validation"
  - `affected_fields`: e.g., `["iva_rate"]`
  - `extracted_values`: Dictionary of successfully extracted fields.
  - `missing_values`: Dictionary of fields needing input.
  - `reason_code`: e.g., "INVALID_EXTRACTED_PERCENTAGE"
- **FR-002**: Technical exceptions (e.g., `ValidationError`, `JSONDecodeError`, pdfplumber/OCR exceptions, filesystem/permission errors) MUST NEVER leak into the user-facing response, system prompt context, or LLM generation output.
- **FR-003**: The Orchestrator MUST transform the domain error contract into a natural language clarification request targeting ONLY the `affected_fields`.
- **FR-004**: All technical exceptions and stack traces MUST be persisted in structured backend logs for diagnostic purposes.
- **FR-005**: The system MUST NOT restart or automatically continue a workflow if a `needs_user_validation` event is emitted. The active workflow MUST block pending user input.

### Key Entities

- **DomainErrorContract**: The structured payload returned by tools when a non-fatal validation or processing error occurs that requires human intervention.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of integration tests verifying validation errors ensure that words like "ValidationError", "Pydantic", "Traceback", or "json" do not appear in the final user response.
- **SC-002**: 100% of the same tests verify that the technical stack trace is successfully recorded in the application logs.
- **SC-003**: Test suite verifies that when `needs_user_validation` is triggered, the system only asks for the explicitly required information (e.g., `affected_fields`) and nothing else.
- **SC-004**: Test suite verifies that emitting a validation error successfully pauses the event bus/workflow, ensuring no subsequent documents in a batch are processed until the user responds.

## Assumptions

- **HIPÓTESIS / DECISIÓN DE ARQUITECTURA A TOMAR**: The exact location where exceptions are caught (e.g., a `ToolExecutionEngine` or `ErrorManager`) is left to the planning phase. We do not assume a specific architectural component currently exists for this, only that the boundary between tool execution and orchestrator response must enforce this contract.
