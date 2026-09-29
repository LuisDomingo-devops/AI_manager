# Feature Specification: Invoice Extraction Pipeline Correction

**Feature Branch**: `015-invoice-extraction-pipeline-correction`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Corregir el pipeline de extracción de facturas para impedir que valores monetarios sean asignados a campos porcentuales. Caso de regresión obligatorio..."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Flawless Extraction of Mixed Formatting (Priority: P1)

Users need their invoices parsed correctly even when monetary values and percentages appear on the same line or in ambiguous layouts.

**Why this priority**: Directly resolves P-06 (validation error due to `iva_rate` = 503.47). Incorrect values break the accounting ledger.

**Independent Test**: Can be tested by providing varied invoice text inputs to `TaxParserService.parse_invoice_text` and asserting that `iva_rate` only ever contains valid percentage boundaries.

**Acceptance Scenarios**:

1. **Given** an invoice containing "total = 41,76 €, base imponible = 34,51 €, IVA = 21%", **When** the extraction pipeline processes it, **Then** it produces `base_amount = 34.51`, `iva_amount = 7.25`, and `iva_rate = 21.0`.
2. **Given** an invoice containing "IVA 503.47 EUR", **When** processed, **Then** it identifies `503.47` as `iva_amount` and infers/extracts `iva_rate` appropriately based on the base, rather than stuffing `503.47` into `iva_rate`.

---

### User Story 2 - Resilient Extraction Fallbacks (Priority: P1)

Users should not receive unhandled technical errors (ValidationErrors) when the LLM makes an extraction mistake; the system must auto-correct or gracefully mark it for review.

**Why this priority**: Prevents technical exceptions from leaking to the UI (P-03).

**Independent Test**: Can be tested by returning garbage/monetary values from the LLM prompt response and verifying that the validation layer flags it for human review rather than raising a fatal exception.

**Acceptance Scenarios**:

1. **Given** an LLM output that attempts to assign a monetary amount to a percentage field, **When** the pipeline validates it, **Then** it catches the logical boundary error, marks the invoice as requiring manual confirmation, and DOES NOT throw a Pydantic `ValidationError` directly to the orchestrator.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST audit and cleanly separate the extraction logic for monetary amounts, percentages, dates, and identifiers prior to Pydantic schema validation.
- **FR-002**: A monetary value (e.g., > 100 in most typical scenarios, or mathematically incompatible with the base/total) MUST NEVER be assigned to a percentage field like `iva_rate`.
- **FR-003**: The pipeline MUST validate percentages against a strict, logical range (e.g., 0.0 to 100.0, or specific legal brackets like 4, 10, 21) before persisting.
- **FR-004**: If the LLM generates an out-of-bounds percentage, the system MUST NOT interpret it as the document's fault or raise an unhandled exception. It must be treated as a low-confidence extraction requiring manual review (`requires_manual_confirmation = True`).
- **FR-005**: The `InvoiceSchema` business logic MUST NOT be loosened or corrupted simply to accept bad LLM data. The extraction service must handle the sanitization.
- **FR-006**: The system MUST include a comprehensive suite of unit tests for the parser that covers:
  - Valid legal percentages: 21%, 10%, 4%.
  - Ambiguous text formatting: "21 %" (with space), "IVA 21%".
  - Decimal separators: amounts with decimal commas (`,`) and decimal points (`.`).
  - Positional variance: total before percentage, total after percentage, multiple amounts on the same line.
  - Regression specific: Ensure the case where `503.47` is incorrectly assigned to `iva_rate` is mathematically impossible under the new parser.

### Key Entities

- **TaxParserService**: The service responsible for reading raw text, prompting the LLM, and calculating implicit rates safely.
- **InvoiceSchema**: The strict data contract representing a valid invoice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the newly added unit tests for `TaxParserService.parse_invoice_text` pass, explicitly validating decimal comma/point variations and the `503.47` regression case.
- **SC-002**: 0 Pydantic `ValidationError` exceptions are leaked to the orchestrator or user due to `iva_rate` exceeding 100.
- **SC-003**: The pipeline successfully calculates `iva_amount = 7.25` and `iva_rate = 21` when given the exact regression case ("total = 41,76 €, base = 34,51 €, IVA = 21%").

## Assumptions

- **HIPÓTESIS**: The current OCR pipeline involves multiple components (potentially pdfplumber, tesseract, vision models) and functions adequately for raw text extraction. The core issue (bug P-06) resides in the LLM prompt extraction logic which does not ask for `iva_rate` explicitly, and the subsequent mathematical inference in `parse_invoice_text`. This hypothesis MUST be verified against the runtime behavior during planning before implementing changes.
