# Research & Decision Log: Saneamiento de Tests e Integridad de Aserciones (Spec 001)

## 1. Problema de Aserciones en Escenarios de Estrés (`test_qa_stress.py`)

### Contexto
En `test_qa_stress.py`, se simulaba una prueba de fatiga y punto de ruptura. Sin embargo, al encontrar una excepción, el script ejecutaba un bloque con `pass` repetidos y finalizaba con `return`. Al terminar con `return`, Pytest interpretaba la función como exitosa (`PASSED`).

### Decisiones de Diseño
- **Decisión**: Eliminar todo `return` anticipado en bloques de excepción.
- **Manejo de Punto de Ruptura**:
  Si el objetivo del test es medir el límite admisible del sistema:
  1. No capturar excepciones silenciosamente.
  2. Si se espera que el sistema soporte hasta `N` transacciones concurrentes sin error, debe asertarse explícitamente:
     `assert not crashed, f"El sistema colapsó en la fase {breaking_stage}: {crash_exception}"`
  3. Los errores de latencia o degradación deben acumularse en una lista y evaluarse con:
     `assert len(errors_encountered) == 0, f"Se detectaron errores durante el estrés: {errors_encountered}"`
- **Alternativas Evaluadas y Rechazadas**:
  - *Rechazada*: Mantener `return` y registrar en consola. (Rechazada porque viola la regla constitucional de tests válidos y maquilla los resultados).

---

## 2. Concurrencia SQLite y Bloqueos de Base de Datos (`test_integration_stress.py`)

### Contexto
En `test_integration_stress.py`, se lanzaban 15 workers simultáneos escribiendo en SQLite sin modo WAL o con pools por defecto, generando errores `database is locked`. El test aceptaba el resultado con `assert len(successful_calls) > 0`, lo cual validaba una prueba aunque el 90% de las llamadas fallasen.

### Decisiones de Diseño
- **Decisión**: Definir un contrato explícito de concurrencia:
  1. Para escrituras directas concurrentes sobre SQLite, comprobar que los workers manejan el timeout o verificar que la política de concurrencia esperada se cumpla de forma exacta.
  2. Sustituir `assert len(successful_calls) > 0` por una aserción estricta de tasa de éxito:
     `assert len(failed_calls) == 0, f"Fallaron {len(failed_calls)} llamadas concurrentes: {failed_calls}"` o, si se prueba deliberadamente saturación, aislar la prueba con expectativas numéricas acotadas y controladas.
- **Alternativas Evaluadas y Rechazadas**:
  - *Rechazada*: Mantener aserciones permisivas tipo `> 0`. (Rechazada porque encubre degradaciones severas y deadlocks).

---

## 3. Triggers de Seguridad Veri*Factu en Tests (`test_coverage_booster.py`)

### Contexto
El archivo `test_coverage_booster.py` ejecutaba:
```python
conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu")
conn.execute("DELETE FROM verifactu_invoices")
```
Esto eliminaba la protección de base de datos que garantiza la inalterabilidad requerida por la normativa antifraude y Veri*Factu.

### Decisiones de Diseño
- **Decisión**:
  1. Prohibir tajantemente el uso de `DROP TRIGGER` en la suite de pruebas.
  2. Para probar el comportamiento con tabla vacía (`0 facturas`), utilizar una conexión temporal con base de datos en memoria (`sqlite3.connect(":memory:")`) donde se inicialice el esquema limpio sin registros previos, preservando intactos todos los triggers de integridad.
- **Alternativas Evaluadas y Rechazadas**:
  - *Rechazada*: Borrar y recrear el trigger tras la prueba. (Rechazada porque contamina la base de datos de test compartida si la aserción falla antes de recrear el trigger).

---

## 4. Reemplazo de Sentencias `pass` en Seeders (`dev_seeder.py`, `legal_seeder.py`)

### Contexto
Tanto en `dev_seeder.py` como en `legal_seeder.py`, se borraron llamadas a `print()` sustituyéndolas por `pass` solitarios entre bloques de inserción SQL y parsing XML.

### Decisiones de Diseño
- **Decisión**:
  1. En `dev_seeder.py`: Reemplazar los `pass` por mensajes informativos estructurados utilizando `app_logger.info(...)`:
     - Inicio de siembra.
     - Limpieza de tablas previas.
     - Registro de número de facturas emitidas y recibidas insertadas.
     - Registro de proyectos y clientes creados.
  2. En `legal_seeder.py`: Reemplazar los `pass` por `app_logger.info(...)` documentando:
     - Solicitud de ley consolidada al BOE.
     - Cantidad de artículos extraídos.
     - Ingestión de lotes completada en ChromaDB.
- **Alternativas Evaluadas y Rechazadas**:
  - *Rechazada*: Dejar las líneas vacías o mantener `pass`. (Rechazada porque los seeders son herramientas operativas y deben proveer observabilidad clara).
