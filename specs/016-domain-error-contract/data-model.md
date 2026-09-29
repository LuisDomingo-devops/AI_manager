# Data Model: Domain Error Contract

## Entities

### `DomainErrorContract` (Pydantic BaseModel)
The standard payload returned by a tool when a non-fatal validation error or processing error occurs requiring user intervention.

**Fields**:
- `status`: `Literal["needs_user_validation", "fatal_error", "system_error"]`
- `affected_fields`: `list[str]` - List of field names that failed validation or are missing.
- `extracted_values`: `dict[str, Any]` - Dictionary of fields that were successfully parsed.
- `missing_values`: `dict[str, Any]` - Dictionary of fields that require input.
- `reason_code`: `str` - A standardized error code (e.g., `INVALID_EXTRACTED_PERCENTAGE`).
- `technical_details`: `Optional[str]` - **INTERNAL USE ONLY**. Stack trace or raw error message. The orchestrator must log this and NEVER send it to the LLM.

## Relationships
- Tools return `DomainErrorContract` (or a `ToolResponse` containing it).
- `PlannerOrchestrator` receives `DomainErrorContract` and translates it to `LLMDecisionEnvelope(type=IntentType.clarification)` or `IntentType.confirmation_required`.

## Validation Rules
- `technical_details` must be strictly excluded from any serialization sent to the LLM context.
