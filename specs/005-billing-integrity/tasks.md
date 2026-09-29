# Tareas de Implementación: 005-billing-integrity

## Phase 1: Setup y Preparación de Entorno

- [x] T001 Crear directorio para logs de ejecución de pruebas en `tests/logs/spec005/`.

---

## Phase 2: User Story 1 (P1) — Endpoint GET /api/v1/billing/invoices y Repositorio

**Meta**: Reparar el método faltante `InvoiceRepository.find_all_invoices()` y conectar el endpoint `GET /api/v1/billing/invoices`.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test de integración en `tests/backend/integration/test_billing_invoices_api_integration.py` que invoque `GET /api/v1/billing/invoices` y demuestre el fallo por método inexistente `find_all_invoices()`.
- [x] T003 [US1] Ejecutar `test_billing_invoices_api_integration.py` y guardar log de fallo (RED) en `tests/logs/spec005/us1_red.log`.

### Implementación (Fase GREEN)
- [x] T004 [US1] Implementar `InvoiceRepository.find_all_invoices(year: Optional[int] = None)` en `app/infrastructure/database/repositories/invoice_repository.py`.
- [x] T005 [US1] Actualizar `list_invoices` en `app/api/v1/billing_router.py` para usar `InvoiceRepository.find_all_invoices(year=year)`.
- [x] T006 [US1] Ejecutar `test_billing_invoices_api_integration.py` y registrar evidencia de aprobación (GREEN) en `tests/logs/spec005/us1_green.log`.

---

## Phase 3: User Story 2 (P1) — Saneamiento de Tests de Billing Products y Services

**Meta**: Eliminar aserciones ambiguas `in (200, 400)` y ramas condicionales que toleren errores en tests de productos y servicios.

### Refactorización y Verificación
- [x] T007 [P] [US2] Saneamiento de `tests/backend/integration/test_billing_products.py` con aserciones estrictas `status_code == 200` y verificación del estado en base de datos.
- [x] T008 [P] [US2] Saneamiento de `tests/backend/integration/test_billing_services.py` con aserciones estrictas `status_code == 200`.
- [x] T009 [US2] Ejecutar ambos tests saneados y guardar log en `tests/logs/spec005/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA y Gobernanza de Facturación

**Meta**: Certificar la integridad criptográfica, consistencia y trazabilidad de las facturas en API y repositorio.

### Tests QA
- [x] T010 [P] [US3] Crear test de QA en `tests/backend/qa/test_billing_governance_suite.py` auditando el ciclo completo de facturas: emisión, listado global, filtrado temporal por año y validación de descifrado.
- [x] T011 [US3] Ejecutar `test_billing_governance_suite.py` y guardar log en `tests/logs/spec005/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T012 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T013 Consolidar commit formal de entrega de la Spec 005.
