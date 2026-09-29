# Research: Domain Error Contract

## NEEDS CLARIFICATION 1: Where to catch exceptions?
**Decision**: We will implement an `ErrorManager` or a decorator at the tool execution boundary (e.g., in a `ToolBase` class or a tool registry executor) that wraps tool calls in a try-except block.
**Rationale**: This prevents every single tool from needing to manually implement exception handling for unexpected errors. Expected validation errors can return a `DomainErrorContract` directly, but unexpected ones will be caught and transformed into a safe contract.
**Alternatives considered**: Catching them directly inside `PlannerOrchestrator`. Rejected because the orchestrator should deal with structured responses, not raw exceptions from various tools.

## DEPENDENCY: Pydantic ValidationErrors
**Decision**: When a `ValidationError` is raised, we will parse the `exc.errors()` to populate the `affected_fields` and `missing_values` in the `DomainErrorContract`.
**Rationale**: Pydantic already provides exact locations of the failing fields, making it trivial to extract which fields need user clarification.

## INTEGRATION: Orchestrator pause mechanism
**Decision**: When the Orchestrator receives a `DomainErrorContract` with status `needs_user_validation`, it will return a `LLMDecisionEnvelope` of type `confirmation_required` (or similar, utilizing `clarification`) containing a prompt generated from the `affected_fields`, and it will STOP the current tool execution loop.
**Rationale**: This adheres to FR-005 (workflow pausing) and ensures the user is prompted synchronously.
