# Tareas de Implementación: 010-database-migration-hygiene

## Phase 1: Setup y Auditoría de Riesgo

- [x] T001 [P] Redactar `docs/audit/migration-risk.md` dando respuesta obligatoria a las 7 preguntas de la Sección 31.12 del Contrato de Discovery.

---

## Phase 2: User Story 1 (P1) — TDD RED

**Meta**: Registrar con tests que `MigrationRunner` debe soportar metadatos normalizados (`VERSION`/`version`, `DESCRIPTION`/`description`) y verificar claves foráneas.

### Tests TDD (Fase RED)
- [x] T002 [P] [US1] Crear test unitario en `tests/backend/unit/test_migration_hygiene_and_runner.py` verificando que todas las versiones cargadas tengan `version` no nula, descripción mayor a 5 caracteres y soporte a minúsculas (`version`/`description`).
- [x] T003 [P] [US1] Crear test de integración en `tests/backend/integration/test_migration_schema_integrity_integration.py` validando la ejecución secuencial completa desde una base limpia y verificando `PRAGMA foreign_key_check`.
- [x] T004 [US1] Ejecutar los tests en fase RED y guardar log en `tests/logs/spec010/us1_red.log`.

---

## Phase 3: User Story 2 (P1) — Implementación TDD GREEN

**Meta**: Saneamiento de `MigrationRunner` sin tocar destructivamente migraciones históricas.

### Implementación (Fase GREEN)
- [x] T005 [US2] En `app/infrastructure/database/migrations.py`, actualizar `load_available_migrations` para soportar `VERSION`/`version` y `DESCRIPTION`/`description`.
- [x] T006 [US2] En `app/infrastructure/database/migrations.py`, añadir método de verificación de integridad referencial `check_foreign_keys(conn)`.
- [x] T007 [US2] Ejecutar `test_migration_hygiene_and_runner.py` y `test_migration_schema_integrity_integration.py` y guardar log en `tests/logs/spec010/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA

**Meta**: Certificar la higiene global del catálogo de migraciones.

### Tests QA
- [x] T008 [P] [US3] Crear suite de QA en `tests/backend/qa/test_migration_hygiene_qa_suite.py` auditando idempotencia estricta, unicidad de secuencias y compatibilidad de SQLite.
- [x] T009 [US3] Ejecutar `test_migration_hygiene_qa_suite.py` y guardar log en `tests/logs/spec010/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T010 Ejecutar la suite completa de pruebas (`pytest -c tests/pytest.ini tests/backend/ -k 'not test_alfonso_invoice_emission_and_processing_until_crash and not test_qa_alfonso_breaking_point' -v`) y certificar 0 regresiones.
- [x] T011 Consolidar commit formal de entrega de la Spec 010.
