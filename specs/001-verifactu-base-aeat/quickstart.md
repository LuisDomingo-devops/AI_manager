# Quickstart Validation Guide: VeriFactu Base

## Prerrequisitos
- Python 3.11+
- Dependencias instaladas: `pip install -r requirements.txt` (incluyendo `pytest`, `lxml`, `httpx`).
- Certificado de pruebas de la AEAT (`test_cert.p12`) ubicado en el directorio raíz o en las variables de entorno.

## Escenario de Validación 1: Generación y Firma
**Objetivo**: Validar que una factura se transforma en XML correcto y se firma (Unit test).
1. Ejecutar el test unitario de esquemas:
   `pytest tests/backend/unit/test_verifactu_schema_and_endpoint_unit.py -v`
**Resultado Esperado**: El test pasa, indicando que el XML generado es válido contra el XSD de VeriFactu y la firma XMLDSig es correcta.

## Escenario de Validación 2: Envío a AEAT Sandbox
**Objetivo**: Validar el envío real/simulado al entorno de pruebas de la AEAT (Integration test).
1. Ejecutar el test de integración de envío:
   `pytest tests/backend/integration/test_verifactu_real_soap.py -v` o `test_verifactu.py`
**Resultado Esperado**: Se recibe un estado `Aceptado` (o el equivalente 200 OK con el XML de respuesta de la AEAT) y se genera un log de ejecución `pytest-logs.txt` en el directorio actual.
