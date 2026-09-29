# Tasks: Aislamiento y Erradicación de Proveedores Falsos (Spec 003)

**Objetivo**: Erradicar la generación y retorno de transacciones inventadas en los adaptadores de proveedores bancarios (`GenericApiProvider`, `PlaidProvider`, `QontoProvider`, `TinkProvider`), garantizando que lancen `NotImplementedError` o `ValueError` según corresponda, y aislar los mocks de la base de datos contable mediante TDD estricto.

---

## Phase 1: Setup y Preparación

- [x] T001 Crear el directorio de logs de ejecución TDD en `tests/logs/spec003/`
- [x] T002 Apuntar `.specify/feature.json` a `specs/003-fake-providers`
- [x] T003 Redactar y certificar `spec.md`, `plan.md` y `tasks.md`

---

## Phase 2: User Story 1 (P1) — Contratos Unitarios de Adaptadores Bancarios

**Meta**: Verificar que los adaptadores no implementados lancen `NotImplementedError` y los adaptadores con integración real requieran credenciales válidas sin inyectar datos ficticios.

### Tests TDD (Red)
- [x] T004 [P] [US1] Crear test unitario en `tests/backend/unit/test_bank_providers_fake_rejection.py` que compruebe que `GenericApiProvider.fetch_transactions`, `PlaidProvider.fetch_transactions` y `QontoProvider.fetch_transactions` lanzan `NotImplementedError`, y que `TinkProvider.fetch_transactions` sin credenciales lanza `ValueError`.
- [x] T005 [US1] Ejecutar `test_bank_providers_fake_rejection.py` y verificar estado Red (fallo porque actualmente devuelven listas con datos hardcodeados).

### Implementación TDD (Green)
- [x] T006 [US1] Modificar `GenericApiProvider` en `app/infrastructure/adapters/bank_providers.py` para lanzar `NotImplementedError` en `fetch_transactions`, `get_auth_link` y `confirm_auth`.
- [x] T007 [US1] Modificar `PlaidProvider` en `app/infrastructure/adapters/bank_providers.py` para lanzar `NotImplementedError` en `fetch_transactions`, `get_auth_link` y `confirm_auth`.
- [x] T008 [US1] Modificar `QontoProvider` en `app/infrastructure/adapters/bank_providers.py` para lanzar `NotImplementedError` en `fetch_transactions`.
- [x] T009 [US1] Modificar `TinkProvider` en `app/infrastructure/adapters/bank_providers.py` eliminando el retorno de transacciones ficticias por defecto y lanzando `ValueError` si faltan credenciales.
- [x] T010 [US1] Actualizar `tests/backend/unit/test_bank_providers_unit.py` para alinear sus aserciones con `NotImplementedError` en vez de esperar datos ficticios.

### Verificación (TDD)
- [x] T011 [US1] Re-ejecutar `test_bank_providers_fake_rejection.py` y `test_bank_providers_unit.py` y guardar log en `tests/logs/spec003/us1_green.log`.

---

## Phase 3: User Story 2 (P1) — Integridad de Sincronización en BankService

**Meta**: Asegurar que `BankService.sync_connection` propague adecuadamente los errores de adaptadores no implementados y no inserte ningún movimiento fantasma en la tabla `bank_movements`.

### Tests TDD (Red)
- [x] T012 [P] [US2] Crear test de integración en `tests/backend/integration/test_bank_sync_integrity.py` verificando que intentar sincronizar conexiones asociadas a `generic`, `plaid` o `qonto` no altera `bank_movements` ni produce asientos contables fantasma.
- [x] T013 [US2] Ejecutar `test_bank_sync_integrity.py` y documentar estado Red.

### Implementación TDD (Green)
- [x] T014 [US2] Ajustar `BankService.sync_connection` en `app/domain/services/bank_service.py` para manejar limpiamente las excepciones de proveedores no implementados.

### Verificación (TDD)
- [x] T015 [US2] Re-ejecutar `test_bank_sync_integrity.py` y guardar log en `tests/logs/spec003/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA y Gobernanza de Proveedores

**Meta**: Certificar con un test de QA exhaustivo que el catálogo de proveedores de producción está 100% libre de inyecciones de datos ficticios.

### Tests TDD
- [x] T016 [P] [US3] Crear test de QA en `tests/backend/qa/test_fake_providers_governance_suite.py` que recorra todos los proveedores de `BankProviderFactory.list_supported_direct_providers()` y verifique que ninguno inyecta datos estáticos en producción.
- [x] T017 [US3] Ejecutar `test_fake_providers_governance_suite.py` y guardar log en `tests/logs/spec003/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T018 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/ -k 'not test_qa_alfonso_breaking_point' -v`) y certificar ausencia de regresiones.
- [x] T019 Consolidar commit formal de entrega de la Spec 003.
