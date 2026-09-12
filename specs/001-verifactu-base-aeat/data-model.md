# Data Model: VeriFactu Base AEAT

## 1. RegistroFacturacion (Factura)
Representa la factura emitida antes de ser serializada.
- `id_emisor` (String): NIF del emisor.
- `num_serie_factura` (String): Número y serie de la factura.
- `fecha_expedicion` (Date): Fecha de emisión.
- `importe_total` (Float): Importe total de la factura.
- `huella_previa` (String, opcional): Hash de la factura anterior (encadenamiento).
- `estado` (Enum): PENDIENTE, ENVIADA, RECHAZADA.

## 2. ConfiguracionVeriFactu
Configuración para comunicarse con la AEAT.
- `certificado_path` (String): Ruta al certificado P12 / PEM.
- `certificado_password` (String): Contraseña del certificado (almacenada segura).
- `url_sandbox` (String): URL del entorno de pruebas.
- `url_produccion` (String): URL de producción de la AEAT.

## 3. RespuestaAEAT
Modelo para la respuesta de los envíos.
- `estado_envio` (String): Aceptado, Rechazado, Aceptado con Errores.
- `csv` (String): Código Seguro de Verificación (si es aceptado).
- `errores` (List[String]): Detalles de errores si fue rechazado.
- `timestamp` (DateTime): Fecha y hora de la respuesta.
