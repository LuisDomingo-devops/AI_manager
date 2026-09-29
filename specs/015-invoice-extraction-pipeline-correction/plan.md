# Implementation Plan: Invoice Extraction Pipeline Correction

**Branch**: `015-invoice-extraction-pipeline-correction` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/015-invoice-extraction-pipeline-correction/spec.md`

## Summary

Corregir el pipeline de extracción de facturas para impedir que valores monetarios sean asignados a campos porcentuales (P-06) y manejar los errores lógicos del LLM como necesidades de confirmación manual, sin lanzar excepciones Pydantic no manejadas (P-03).

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**: Pydantic, GeminiClient

**Storage**: N/A para esta lógica pura de extracción.

**Testing**: pytest (unit tests y integration tests)

**Target Platform**: Backend server

**Project Type**: Backend Module / Service (`TaxParserService`)

**Performance Goals**: N/A

**Constraints**: Validación estricta; las excepciones de validación Pydantic por errores del LLM deben encapsularse y resolverse mediante validación secundaria y marcado como `requires_manual_confirmation`.

**Scale/Scope**: Limitado al servicio de parseo y el esquema `InvoiceSchema`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Desarrollo en Español**: Todo se redactará en español.
- **II. TDD Estricto**: Se escribirán tests unitarios primero.
- **III. Cobertura Completa**: Tests unitarios cubrirán todas las variaciones de campos porcentuales.
- **IV. Ejecución Continua y Log**: Se generarán logs de tests post-implementación.

## Project Structure

### Documentation (this feature)

```text
specs/015-invoice-extraction-pipeline-correction/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md (se generará luego)
```

### Source Code (repository root)

```text
app/
├── domain/
│   └── services/
│       └── tax_parser_service.py
├── schemas/
│   └── invoice_schema.py

tests/
├── unit/
│   └── test_tax_parser_service.py
```

**Structure Decision**: El proyecto es un monolito en Python bajo el directorio `app/`. La corrección se centralizará en los servicios de dominio de parsing y los esquemas Pydantic correspondientes.
