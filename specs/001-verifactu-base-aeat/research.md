# Research: VeriFactu & AEAT Integration

## Certificados de Prueba
- **Decisión**: Se utilizarán los certificados de prueba que están ubicados en la carpeta `data/certificados_prueba`.
- **Razón**: Permite realizar las pruebas y desarrollo utilizando la pasarela sandbox/preproducción de la AEAT (`prewww10.aeat.es`) sin afectar el entorno real. El usuario ha confirmado su disponibilidad.

## Criptografía XMLDSig
- **Decisión**: Se utilizará `signxml` (o la librería más apropiada disponible en el entorno) para firmar los payload XML.
- **Razón**: `signxml` soporta los estándares de XMLDSig requeridos por la AEAT (inclusive algoritmos y transformaciones C14N como http://www.w3.org/TR/2001/REC-xml-c14n-20010315).

## Chaining y Hashes SIF
- **Decisión**: Los hashes `prev_event_hash` y `current_hash` deben ser firmemente calculados con SHA-256 usando UTF-8 según lo define la Orden Ministerial, antes de firmar el XML.
- **Razón**: Inmutabilidad. Cualquier desajuste provocaría el rechazo de la factura actual y las posteriores por la AEAT.
