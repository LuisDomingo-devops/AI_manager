# Implementation Tasks: Invoice Extraction Pipeline Correction

**Feature**: `015-invoice-extraction-pipeline-correction`

## Phase 1: Setup
**Purpose**: No new foundational setup is required as the project structure already exists.

## Phase 2: Foundational (Blocking Prerequisites)
**Purpose**: Prerrequisitos de configuración (Vacío para esta corrección menor).

---

## Phase 3: User Story 1 - Flawless Extraction of Mixed Formatting (Priority: P1)
**Goal**: Impedir que los valores monetarios se asignen a los porcentajes debido a formatos mixtos.

### Tests for User Story 1 (TDD - MUST FAIL INITIALLY)
- [x] T001 [P] [US1] Crear test unitario en `tests/unit/test_tax_parser_service.py` que inyecte un texto con formato mixto (ej: "IVA 503.47 EUR") para probar que la tasa no acaba en `iva_rate` (Regresión P-06).

### Implementation for User Story 1
- [x] T002 [US1] Actualizar la lógica de `TaxParserService.parse_invoice_text` en `app/domain/services/tax_parser_service.py` para intercambiar `iva_rate` e `iva_amount` si el rate supera 100 y coincide lógicamente con el amount.
- [x] T003 [US1] Reforzar la desinfección de símbolos monetarios (`€`, `EUR`, `\$`) antes de asignar los campos numéricos en `app/domain/services/tax_parser_service.py`.

---

## Phase 4: User Story 2 - Resilient Extraction Fallbacks (Priority: P1)
**Goal**: Manejar excepciones de Pydantic sin romper la ejecución, marcando la extracción para confirmación manual.

### Tests for User Story 2 (TDD - MUST FAIL INITIALLY)
- [x] T004 [P] [US2] Crear test unitario en `tests/unit/test_tax_parser_service.py` que provea datos deliberadamente erróneos/incompatibles y verifique que se retorna `requires_manual_confirmation = True` en vez de propagar `ValidationError`.

### Implementation for User Story 2
- [x] T005 [US2] Envolver la instanciación de `InvoiceSchema` (y/u otra lógica LLM) en `app/domain/services/tax_parser_service.py` en un bloque `try-except` para atrapar fallos de validación, retornando un objeto parcial/seguro con `requires_manual_confirmation = True`.

---

## Phase 5: Polish & Cross-Cutting Concerns
**Purpose**: Validation and code cleanliness.
- [x] T006 Ejecutar todos los tests (Unitarios e Integración) con `uv run pytest` y verificar 100% de éxito, guardando el log de salida (Regla IV de la Constitución).
- [x] T007 Validar el quickstart con `uv run pytest tests/unit/test_tax_parser_service.py -v`.

---

## Dependencies & Execution Order
- **User Story 1**: Puede comenzar de inmediato.
- **User Story 2**: Puede comenzar de inmediato, pero idealmente tras T003 para unificar la limpieza de datos en un solo pase sobre `tax_parser_service.py`.
- **Polish**: Ejecutar al finalizar US1 y US2.

## Parallel Opportunities
- T001 y T004 (creación de tests de ambas US) pueden ser trabajadas en paralelo por distintos desarrolladores ya que son funciones de test diferentes.
