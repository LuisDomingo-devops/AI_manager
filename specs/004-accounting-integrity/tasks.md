# Tasks: Integridad Contable, Asientos y Partida Doble (Spec 004)

**Objetivo**: Subsanar el `NameError` silenciado de `LedgerService` en `CollectionService.register_payment()`, garantizar la persistencia atómica del asiento contable de cobro en el Libro Diario y Mayor, validar el principio de partida doble y certificar el aislamiento multitenant según la Sección 6 del Contrato de Discovery.

---

## Phase 1: Setup y Preparación

- [x] T001 Crear el directorio de logs de ejecución TDD en `tests/logs/spec004/`
- [x] T002 Apuntar `.specify/feature.json` a `specs/004-accounting-integrity`
- [x] T003 Redactar y certificar `spec.md`, `plan.md` y `tasks.md`

---

## Phase 2: User Story 1 (P1) — Persistencia y Verificabilidad del Asiento de Cobro

**Meta**: Certificar que al registrar un pago en `CollectionService.register_payment()`, el asiento contable se crea obligatoriamente en `journal_entries` y `ledger_entries`.

### Tests TDD (Red)
- [x] T004 [P] [US1] Crear test de integración en `tests/backend/integration/test_payment_ledger_integration.py` verificando que un cobro registrado genera un asiento contable verificable con cuentas 570/572 al Debe y 430 al Haber.
- [x] T005 [US1] Ejecutar `test_payment_ledger_integration.py` y verificar estado Red (fallo porque actualmente `LedgerService` no está importado y el apunte nunca se crea en la base de datos).

### Implementación TDD (Green)
- [x] T006 [US1] Importar `LedgerService` en `app/domain/services/collection_service.py` y asegurar consistencia transaccional atómica entre `payments` y `journal_entries`.

### Verificación (TDD)
- [x] T007 [US1] Re-ejecutar `test_payment_ledger_integration.py` y guardar log en `tests/logs/spec004/us1_green.log`.

---

## Phase 3: User Story 2 (P1) — Contratos de Partida Doble y Ejercicios Cerrados

**Meta**: Validar que `LedgerService` impida rigurosamente la inserción de asientos descuadrados o en ejercicios fiscales cerrados.

### Tests TDD
- [x] T008 [P] [US2] Crear test unitario en `tests/backend/unit/test_double_entry_and_fiscal_year_contracts.py` verificando que asientos descuadrados lanzan `ValueError` ("Partida Doble rota") y que fechas en años cerrados son bloqueadas.
- [x] T009 [US2] Ejecutar `test_double_entry_and_fiscal_year_contracts.py` y guardar log en `tests/logs/spec004/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA y Gobernanza de la Cadena Contable

**Meta**: Certificar la cadena completa: `payment -> ledger entry -> double-entry integrity -> tenant isolation`.

### Tests TDD
- [x] T010 [P] [US3] Crear test de QA en `tests/backend/qa/test_accounting_integrity_governance_suite.py` que compruebe la integridad de la cadena de cobro, la cuadratura contable y el aislamiento total entre dos inquilinos (`tenant_a` y `tenant_b`).
- [x] T011 [US3] Ejecutar `test_accounting_integrity_governance_suite.py` y guardar log en `tests/logs/spec004/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T012 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/ -k 'not test_qa_alfonso_breaking_point' -v`) y certificar ausencia de regresiones colaterales.
- [x] T013 Consolidar commit formal de entrega de la Spec 004.
