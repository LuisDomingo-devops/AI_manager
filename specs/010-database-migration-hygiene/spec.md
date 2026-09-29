# Especificación de Requisitos: 010-database-migration-hygiene

## Resumen Ejecutivo

Conforme a las Secciones 18 y 31.12 del Contrato de Discovery (`docs/audit/discovery-contract.md`), el sistema de persistencia y migraciones evolutivas debe ser auditado, saneado y documentado con rigor técnico:
1. No se debe modificar destructivamente la historia de migraciones existentes si no se puede determinar fehacientemente su estado en producción (`UNKNOWN — production migration history unavailable`).
2. Se debe generar el documento auditable `docs/audit/migration-risk.md` dando respuesta explícita y verificada a las 7 preguntas normativas de la Sección 31.12.
3. El motor de migraciones (`MigrationRunner` en `app/infrastructure/database/migrations.py`) debe ser tolerante y homogéneo al cargar metadatos de versiones (`VERSION` y `version`, `DESCRIPTION` y `description`) y verificar la integridad referencial y de esquema tras la ejecución.

---

## Criterios de Aceptación (Gherkin)

### Escenario 1: Normalización de metadatos de migración en MigrationRunner
**Dado** un módulo de migración en `migrations/versions/` que defina metadatos en mayúsculas (`VERSION`, `DESCRIPTION`) o minúsculas (`version`, `description`) o carezca de ellos,  
**Cuando** `MigrationRunner.load_available_migrations()` procesa los archivos,  
**Entonces** todas las instancias de `Migration` deben contar con `version` válida y `description` descriptiva sin lanzar excepciones y ordenadas ascendentemente.

### Escenario 2: Verificación de integridad referencial post-migración
**Dado** un entorno SQLite nuevo donde se aplican todas las migraciones históricas (000 a 023),  
**Cuando** finaliza `MigrationRunner.run_pending_migrations(conn)`,  
**Entonces** no deben existir violaciones de claves foráneas (`PRAGMA foreign_key_check` vacío) ni fallos de acceso a columnas ordinales.

### Escenario 3: Generación del informe formal de riesgos de migración
**Dado** el contrato de Discovery en sus secciones 18 y 31.12,  
**Cuando** se audita el catálogo completo de migraciones,  
**Entonces** el archivo `docs/audit/migration-risk.md` debe responder con evidencia demostrable a cada una de las preguntas requeridas.
