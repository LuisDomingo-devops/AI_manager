# Quickstart: Validación de VeriFactu (AEAT)

## Escenario de Validación 1: Envío de Factura Exitosa al Sandbox AEAT
Este escenario valida que el encadenamiento de facturas, la firma XMLDSig y la conexión con el sandbox prewww10.aeat.es funcionan correctamente.

**Prerequisites**: 
- Los certificados de prueba proporcionados en `data/certificados_prueba` cargados en la base de datos o disponibles vía `app.config`.

**Test Command**:
```bash
venv\Scripts\python.exe -m pytest tests\backend\integration\test_verifactu.py -v
```

**Expected Outcome**:
El test de integración debe pasar. Se conectará (o mockeará condicionalmente si configurado así, pero verificará la firma) y la AEAT debe responder `HTTP 200` y `status="accepted"`.

## Escenario de Validación 2: Inmutabilidad (Hash Chaining)
Este escenario valida que si se altera un hash anterior, se rompe la cadena.

**Test Command**:
```bash
venv\Scripts\python.exe -m pytest tests\backend\integration\test_verifactu_integrity.py -v
```

**Expected Outcome**:
La alteración del `sif_event_log` debe lanzar una excepción o fallar, indicando que el trigger de inmutabilidad fiscal ha prevenido la manipulación o el test verifica que los hashes se rompen si se altera a nivel bajo.
