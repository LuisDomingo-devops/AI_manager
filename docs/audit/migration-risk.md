# Informe de Riesgos de Migración (Migration Risk Assessment)

**Proyecto**: Alfonso Autónomo — AI Manager  
**Fecha de Auditoría**: 2026-09-29  
**Sección de Referencia**: Discovery Contract (§ 18 y § 31.12)  
**Estado General de la Historia de Migraciones en Producción**:  
`UNKNOWN — production migration history unavailable`

---

## 1. Respuestas Obligatorias a las 7 Preguntas de Discovery (§ 31.12)

### 1. ¿Hay migraciones duplicadas?
- **Respuesta**: **NO**.
- **Evidencia**: Se han auditado los 21 archivos ubicados en `migrations/versions/`. Cada archivo cuenta con un prefijo numérico único (`000` a `014`, `016`, `019` a `023`). No existen colisiones de número de versión. Existen huecos deliberados en la secuencia numérica (`015`, `017`, `018`), pero ninguna versión está repetida.

### 2. ¿Hay migraciones contradictorias?
- **Respuesta**: **NO en conflicto activo**, pero existen refinamientos sucesivos.
- **Evidencia**: 
  - La migración `002` definió inicialmente la tabla `sif_event_log`, y posteriormente la migración `005` (`005_fix_sif_event_log_schema.py`) reconstruyó y normalizó atómicamente dicha tabla para incorporar `current_hash` y `prev_event_hash`.
  - La migración `012` consolida el esquema canónico Verifactu/SIF. Ambas conviven mediante comprobaciones condicionales `CREATE TABLE IF NOT EXISTS` y `ALTER TABLE`.

### 3. ¿Hay tablas creadas y eliminadas?
- **Respuesta**: **SÍ**.
- **Evidencia**: 
  - La tabla `bank_transfers` (creada en fases iniciales para transferencias PSD2) fue explícitamente eliminada en la migración `022_remove_bank_transfers.py` mediante la sentencia `DROP TABLE IF EXISTS bank_transfers` debido a la deprecación de los flujos de pago bancario directo PSD2.

### 4. ¿Hay migraciones con mojibake?
- **Respuesta**: **SÍ en comentarios y docstrings históricos**.
- **Evidencia**: 
  - En los archivos `002_verifactu_sif_fiscal_year.py`, `005_fix_sif_event_log_schema.py`, `007_asset_depreciation.py` y `010_invoice_tax_engine_audit.py` se detectaron descripciones y comentarios codificados en Latin-1/Windows-1252 que se visualizan como `Reconstruccin`, `auditora` o `inversin`.
  - El motor `MigrationRunner` maneja los archivos en modo texto UTF-8 con fallback a ascii en tiempo de ejecución para evitar caídas.

### 5. ¿Se modifica schema histórico?
- **Respuesta**: **NO destructivamente**.
- **Evidencia**: Las migraciones históricas existentes se mantienen inmutables conforme al mandato § 18 del Discovery Contract ("NO reescribas la historia de migraciones existentes a ciegas"). Cualquier ampliación se realiza exclusivamente vía `ALTER TABLE ... ADD COLUMN` o creación de tablas auxiliares.

### 6. ¿Existe riesgo de haber sido aplicado en producción?
- **Respuesta**: **UNKNOWN — production migration history unavailable**.
- **Justificación**: Al no disponer de un volcado verificado de la base de datos de producción ni de la tabla `schema_migrations` de un entorno productivo real, se asume por principio de prudencia técnica que las migraciones `000` a `023` pueden haber sido ejecutadas total o parcialmente en entornos reales. Por ello, **está estrictamente prohibido reescribir o eliminar migraciones históricas**.

### 7. ¿Puede solucionarse con una nueva migración?
- **Respuesta**: **SÍ**.
- **Evidencia**: Cualquier ajuste futuro de esquema, índices o saneamiento de integridad referencial debe realizarse creando una nueva migración con número de versión incremental (por ejemplo `024_...`), preservando el principio de inmutabilidad histórica.

---

## 2. Recomendaciones de Higiene para MigrationRunner

1. **Soporte insensible a mayúsculas/minúsculas para metadatos**:
   `MigrationRunner` debe inspeccionar `VERSION` o `version` y `DESCRIPTION` o `description`, con fallback limpio al nombre del archivo (`file.stem`).
2. **Chequeo de Integridad de Claves Foráneas**:
   Añadir la capacidad en el runner de evaluar `PRAGMA foreign_key_check` para alertar de referencias rotas en entornos de desarrollo y testing.
3. **Acceso Seguro a Columnas en SQLite**:
   Garantizar que todas las migraciones inspeccionen `PRAGMA table_info` accediendo por tupla ordinal `row[1]` o por clave `row["name"]` según el tipo devuelto.
