# Tareas de Implementación: 006-stripe-idempotency

## Phase 1: Setup y Preparación de Entorno

- [x] T001 Crear directorio para logs de ejecución de pruebas en `tests/logs/spec006/`.

---

## Phase 2: User Story 1 (P1) — TDD RED (Fallo Verificado por Ausencia de DATA_DIR y Falta de Idempotencia)

**Meta**: Demostrar con evidencia reproducible que `DATA_DIR` no existe en `app.utils.paths` y que el webhook actual no tiene idempotencia garantizada.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_paths_data_dir.py` para comprobar la existencia y tipo de `DATA_DIR` en `app.utils.paths`.
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_stripe_webhook_idempotency_integration.py` que envíe dos veces el mismo evento de Stripe y verifique que la segunda invocación devuelve `status == "ignored"` y `reason == "already_processed"`, sin invocar `provision_new_tenant`.
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log de evidencia en `tests/logs/spec006/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Resolver la exportación de `DATA_DIR` y el mecanismo de idempotencia en producción.

### Implementación (Fase GREEN)
- [x] T005 [US2] Definir y exportar `DATA_DIR` en `app/utils/paths.py` apuntando a la carpeta `data/` del proyecto y asegurando su creación.
- [x] T006 [US2] Refactorizar la gestión de idempotencia en `app/api/v1/subscriptions_router.py`: importar `DATA_DIR`, gestionar lectura y escritura atómica/segura de `stripe_events.json`, y responder `{"status": "ignored", "reason": "already_processed", "event": event_type}` sin volver a aprovisionar ni enmascarar errores de forma permisiva.
- [x] T007 [US2] Ejecutar `test_paths_data_dir.py` y `test_stripe_webhook_idempotency_integration.py`, registrando pase en verde en `tests/logs/spec006/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — QA y Resiliencia de Idempotencia

**Meta**: Certificar resiliencia ante múltiples eventos, eventos corruptos y persistencia.

### Tests QA
- [x] T008 [P] [US3] Crear suite de QA en `tests/backend/qa/test_stripe_idempotency_qa_suite.py` que compruebe la acumulación de múltiples eventos únicos y la recuperación ante archivos JSON vacíos o con formato inválido.
- [x] T009 [US3] Ejecutar `test_stripe_idempotency_qa_suite.py` y guardar log en `tests/logs/spec006/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T010 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T011 Consolidar commit formal de entrega de la Spec 006.
