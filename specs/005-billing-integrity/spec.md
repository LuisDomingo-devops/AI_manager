# Especificación: 005-billing-integrity (Integridad de Facturación y Repositorios)

## Contexto
El Contrato de Discovery técnico (Sección 7: BILLING y Sección 5: TESTS INVÁLIDOS) identifica anomalías críticas en el subsistema de facturación:
1. En `app/api/v1/billing_router.py`, el endpoint `GET /api/v1/billing/invoices` intenta invocar `InvoiceRepository.find_all_invoices()`, método inexistente que provoca un `AttributeError` en tiempo de ejecución.
2. En `tests/backend/integration/test_billing_products.py` y `test_billing_services.py`, existen assertions inválidas (`assert response.status_code in (200, 400)`, bloques `if response.status_code == 200:` sin aserciones deterministas) que enmascaran errores de contrato.

## Problema
- `GET /api/v1/billing/invoices` falla con error 500 (`AttributeError: type object 'InvoiceRepository' has no attribute 'find_all_invoices'`).
- Los tests de productos y servicios no garantizan que la API responda con el código HTTP y datos esperados según el contrato real.

## Comportamiento Actual
- `InvoiceRepository` dispone de métodos como `save`, `find_invoice_by_id`, `get_pending_invoices`, pero carece de un método para listar todas las facturas descifradas (`find_all_invoices`).
- Los tests de facturación aceptan indistintamente respuestas 200 y 400.

## Comportamiento Esperado
1. `InvoiceRepository` expone `find_all_invoices(year: Optional[int] = None)` que recupera y descifra de forma segura todas las facturas del inquilino activo.
2. `billing_router.py` consume `InvoiceRepository.find_all_invoices(year=year)` y retorna la lista completa y consistente de facturas con código HTTP 200.
3. `test_billing_products.py` y `test_billing_services.py` contienen assertions estrictas y unívocas sobre el código HTTP (200 OK) y las propiedades persistidas.

## Requisitos Funcionales
- **RF-001**: `InvoiceRepository.find_all_invoices()` debe retornar una lista de diccionarios con los campos descifrados de cada factura: `db_id`, `invoice_id`, `date`, `issuer_name`, `issuer_nif`, `receiver_name`, `receiver_nif`, `base_imponible`, `iva_rate`, `iva_amount`, `irpf_rate`, `irpf_amount`, `total_amount`, `status`, `concept`, `category`, `year`, `quarter`.
- **RF-002**: `GET /api/v1/billing/invoices` debe responder con HTTP 200 y un JSON `{"status": "ok", "total": N, "invoices": [...]}`.
- **RF-003**: Soporte opcional para el parámetro de consulta `?year=YYYY`.
- **RF-004**: Los tests de integración de productos y servicios no deben contener `in (200, 400)` ni condiciones débiles que oculten fallos de creación o borrado.

## Requisitos No Funcionales & Invariantes
- Invariante de Cifrado: Todo dato sensible almacenado en `invoices` debe descifrarse transparentemente vía `encryptor.decrypt()`.
- Tolerancia a registros corruptos con registro en `error_logger`.
- Preservar compatibilidad total con la suite existente sin regresiones.

## Tests Requeridos
1. **Unitario / Integración**:
   - `test_billing_invoices_api_integration.py`: Test que invoque `GET /api/v1/billing/invoices` y valide la recuperación de facturas existentes y filtrado por año.
2. **Saneamiento**:
   - `test_billing_products.py` y `test_billing_services.py` saneados con assertions deterministas.
3. **QA**:
   - `test_billing_governance_suite.py`: Prueba de gobernanza de ciclo completo de facturación (creación, listado global, filtrado por año y consistencia criptográfica).
