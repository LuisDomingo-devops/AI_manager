# Data Model: VeriFactu (AEAT)

## Entities

### RegistroFacturacion (verifactu_invoices)
Representa la factura procesada y lista para enviarse al Sistema VeriFactu.
- **Fields**:
  - `invoice_id`: String, UUID referenciando la factura en `invoices`.
  - `status`: String, ['pending', 'accepted', 'accepted_with_errors', 'rejected'].
  - `xml_payload`: Text, El XML completo y firmado generado para la factura.
  - `aeat_response_code`: String, Código HTTP/SOAP de la AEAT.
  - `aeat_csv`: String, Código Seguro de Verificación proporcionado por la AEAT.
- **Constraints**: 
  - `invoice_id` debe existir en la tabla `invoices`.

### SIFEventLog (sif_event_log)
Registro de auditoría de eventos de facturación para inmutabilidad (Orden HAC/1177/2024).
- **Fields**:
  - `id`: Integer, auto-incremental.
  - `event_type`: String.
  - `invoice_id`: String, UUID de la factura implicada.
  - `prev_event_hash`: String, SHA-256 del evento inmediatamente anterior.
  - `current_hash`: String, SHA-256 de los datos de este evento + el `prev_event_hash`.
  - `created_at`: Timestamp.
- **Constraints**: 
  - La cadena no puede ser alterada (inmutabilidad por Triggers).

### ConfiguracionVeriFactu / Certificados (certificates)
Entidad para almacenar certificados X509.
- **Fields**:
  - `id`: Integer.
  - `name`: String, alias.
  - `cert_data`: Blob/Text, cifrado con AES.
  - `private_key`: Blob/Text, cifrado con AES.
  - `passphrase`: Blob/Text, cifrado con AES.
