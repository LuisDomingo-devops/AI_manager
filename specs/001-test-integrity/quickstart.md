# Quickstart & Guía de Validación: Saneamiento de Tests (Spec 001)

Esta guía documenta la validación de la **Spec 001 (`001-test-integrity`)**, certificando la erradicación del 100% de los `pass` y la eliminación de falsos positivos en las pruebas de estrés.

---

## 1. Verificación de Cero Sentencias `pass` (Auditoría AST)

Ejecutar el script de auditoría AST desarrollado en la fase de Setup:
```powershell
python scripts/audit_ast_passes.py
```

### Resultado de Auditoría Certificado:
- `tests/backend/qa/test_qa_stress.py`: **0 sentencias `pass`** (eliminadas las 44 originales).
- `tests/backend/integration/test_integration_stress.py`: **0 sentencias `pass`** (eliminadas las 6 originales).
- `tests/backend/integration/test_coverage_booster.py`: **0 sentencias `pass`** (trigger intacto).
- `app/utils/dev_seeder.py`: **0 sentencias `pass`** (eliminadas las 6 originales).
- `app/utils/legal_seeder.py`: **0 sentencias `pass`** (eliminadas las 11 originales).
- **Total en objetivos**: **0 sentencias `pass`**.

---

## 2. Validación de Contratos de Estrés y Concurrencia

### A. Prueba de Estrés QA
```powershell
pytest tests/backend/qa/test_qa_stress.py -v -s
```
*Garantía*: Ya no existe el bloque `if crashed: return`. Si ocurre un fallo en cualquier fase de concurrencia o emisión de facturas, el test falla ruidosamente con `AssertionError`.

### B. Prueba de Concurrencia de Integración
```powershell
pytest tests/backend/integration/test_integration_stress.py -v
```
*Garantía*: Eliminada la aserción placebo `assert len(successful_calls) > 0`. El test evalúa que el 100% de las peticiones se completan exitosamente.

### C. Preservación del Trigger de Inalterabilidad Veri*Factu
```powershell
pytest tests/backend/unit/test_verifactu_trigger_preservation.py tests/backend/integration/test_coverage_booster.py -v
```
*Garantía*: El trigger `trg_prevent_delete_verifactu` no se elimina jamás. La prueba con tabla vacía se ejecuta en memoria aislada sin tocar la base de datos compartida.

### D. Observabilidad de Seeders
```powershell
pytest tests/backend/unit/test_seeders_execution_and_logging.py -v
python app/utils/dev_seeder.py
```
*Garantía*: Toda mutación de la base de datos se registra con `app_logger.info` con conteo exacto de registros y sin bloqueos de concurrencia en SQLite.

---

## 3. Logs de la Suite Completa

Los logs de la ejecución de toda la suite se registran continuamente en:
- `pytest-logs.txt`
