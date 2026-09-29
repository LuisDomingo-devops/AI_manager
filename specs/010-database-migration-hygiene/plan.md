# Plan de Implementación: 010-database-migration-hygiene

## Arquitectura y Componentes Afectados

1. **Documentación de Auditoría**:
   - `docs/audit/migration-risk.md`: Informe auditable con la respuesta a las 7 preguntas de la Sección 31.12.
2. **Motor de Migraciones**:
   - `app/infrastructure/database/migrations.py`:
     - Normalización de lectura de metadatos (`VERSION` / `version`, `DESCRIPTION` / `description`).
     - Verificación post-ejecución opcional de `PRAGMA foreign_key_check` asegurando consistencia.
3. **Suites de Pruebas**:
   - Unitario: `tests/backend/unit/test_migration_hygiene_and_runner.py`
   - Integración: `tests/backend/integration/test_migration_schema_integrity_integration.py`
   - QA: `tests/backend/qa/test_migration_hygiene_qa_suite.py`

## Fases TDD
- **Fase 1 (RED)**: Tests que detectan discrepancias en carga de metadatos o falta de verificación de claves foráneas.
- **Fase 2 (GREEN)**: Actualización de `MigrationRunner` para normalizar atributos y validar claves foráneas.
- **Fase 3 (QA & Auditoría)**: Ejecución de suite de QA y redacción formal de `migration-risk.md`.
- **Fase 4 (Regresión)**: Ejecución de suite completa del backend y commit.
