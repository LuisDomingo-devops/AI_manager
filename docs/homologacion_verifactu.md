# DOCUMENTO DE REQUISITOS TÉCNICOS Y NORMAS DEL PROYECTO: MÓDULO VERIFACTU (ESPAÑA)

## 1. CONTEXTO Y MARCO LEGAL
Este documento define las reglas de desarrollo e implementación para el Sistema Informático de Facturación (SIF) del proyecto. El software debe cumplir estrictamente con el Real Decreto 1007/2023 (Ley Antifraude / VeriFactu) de la Agencia Estatal de Administración Tributaria (AEAT) de España.

Hacienda no realiza una homologación directa mediante examen del software; exige que el fabricante emita una **Declaración Responsable** legal certificando que el sistema impide activamente la contabilidad paralela o "B".

### Fechas Límite de Obligatoriedad (Entorno Real)
*   **Empresas**: 1 de enero de 2027.
*   **Autónomos**: 1 de julio de 2027.

---

## 2. PRINCIPIOS ARQUITECTÓNICOS OBLIGATORIOS (LOS 6 PILARES)
El LLM debe rechazar cualquier propuesta de código o arquitectura de base de datos que rompa los siguientes principios sobre los registros de facturación:
1.  **Inalterabilidad**: Queda estrictamente prohibido modificar (`UPDATE`) o eliminar (`DELETE`) cualquier registro de factura guardado o emitido.
2.  **Trazabilidad**: Las facturas deben estar encadenadas cronológicamente de forma auditable.
3.  **Integridad**: El sistema debe blindar los datos frente a manipulaciones externas o alteraciones del histórico.
4.  **Conservación**: Los datos deben almacenarse de forma segura, estructurada y completa a largo plazo.
5.  **Accesibilidad**: Debe existir una herramienta ágil para exportar o inspeccionar los datos por parte de la administración.
6.  **Legibilidad**: Los formatos de almacenamiento y exportación deben ceñirse estrictamente al estándar XML de la AEAT.

---

## 3. ESPECIFICACIONES TÉCNICAS (STACK PYTHON)

### 3.1. Encadenamiento Criptográfico (Chaining)
Cada factura emitida debe calcular un hash criptográfico **SHA-256** codificado obligatoriamente en **Base64** que concatene de forma exacta los siguientes campos del registro actual con el hash del registro anterior:
*   `hash_anterior` 
*   `nif_emisor`
*   `num_factura`
*   `fecha_expedicion`
*   `importe_total`

*Reglas de negocio para el Hash:*
*   Validar siempre que la cadena de texto esté normalizada en formato UTF-8 antes de aplicar el algoritmo hash.
*   **Factura Inicial (Primer Registro)**: Para la primerísima factura de un emisor en el sistema, la AEAT prohíbe usar una cadena de ceros. El campo del hash anterior se debe omitir visualmente en el XML y se debe marcar el indicador o etiqueta específica de "Primer registro" o "Factura inicial" según las especificaciones técnicas del esquema de la AEAT.

### 3.2. Estructura y Firma Electrónica (XAdES)
*   **Formatos XML**: El sistema debe gestionar dos tipos de esquemas XML independientes según la acción del usuario: `RegistroFacturacionAlta` (para emitir nuevas facturas) y `RegistroFacturacionAnulacion` (para cancelar facturas emitidas por error). Si un usuario se equivoca, **está prohibido modificar la factura**; se debe emitir obligatoriamente una Anulación. Ambos esquemas mantienen el encadenamiento criptográfico con el registro inmediatamente anterior de la base de datos (sea este de alta o de anulación).
*   **Firma**: Cada archivo XML generado debe firmarse digitalmente utilizando la política de firma avanzada **XAdES** (específicamente **XAdES-BES**, Enveloped signature) empleando un certificado electrónico cualificado (FNMT, Camerfirma, etc.).
*   **Librerías sugeridas**: `lxml` para manipulación de XML, `signxml` o `pyXAdES` para la firma y `hashlib` junto con `base64` para el algoritmo del hash.

### 3.3. Comunicaciones y Envío Inmediato (VeriFactu)
El sistema opera bajo la modalidad de remisión automática en tiempo real:
*   **Protocolo**: Servicios web basados en **SOAP** (con seguridad WS-Security) o **REST** mTLS (Mutual TLS) utilizando los endpoints oficiales de la AEAT.
*   **Librerías de comunicación**: `zeep` acoplada con `requests` para gestionar las sesiones seguras y los certificados públicos/privados en formato `.pem`.
*   **Lógica Asíncrona y Modo Offline**: 
    *   El envío debe ejecutarse de forma asíncrona para no bloquear la interfaz del usuario.
    *   Si el servidor de la AEAT falla o el usuario no tiene conexión a internet (Modo Offline), la aplicación **debe almacenar los XML firmados en una cola local persistente** (ej. PostgreSQL/SQLite).
    *   Se deben ejecutar reintentos automáticos periódicos en segundo plano en cuanto se restablezca la conexión hasta confirmar la recepción.
    *   Debe registrarse y procesarse el estado exacto de la respuesta devuelta por Hacienda (`Aceptado`, `Aceptado con errores`, `Rechazado`).

### 3.4. Registro de Eventos (Audit Log)
Debe implementarse un archivo de log o tabla de auditoría interna inalterable que registre de manera automática:
*   Inicios y cierres de sesión del personal.
*   Altas, bajas o cambios críticos en la configuración del software.
*   Errores y excepciones de red en la comunicación con la AEAT.
*   Actualizaciones del código o despliegues del sistema.

### 3.5. Correcciones Técnicas de Última Hora e Implementación Python (AEAT)
*   **Formato de Hash definitivo**: Queda descartado el uso de cadenas hexadecimales (`.hexdigest().upper()`). El hash SHA-256 final enviado en el XML debe estar codificado obligatoriamente en **Base64** estándar. 
    *   *Snippet de implementación en Python:* `base64.b64encode(hash_bytes).decode('utf-8')` utilizando el método `.digest()` previo.
*   **Estructura de la URL para el QR**: La URL base obligatoria para el entorno de cotejo es la oficial de la AEAT: `https://agenciatributaria.gob.es` (o la URL base simplificada `https://agenciatributaria.gob.es` si así lo actualiza la documentación oficial de producción). Los parámetros exactos pasados por GET son únicamente: `id` (NIF emisor), `num` (Número de factura), `fecha` (Fecha de expedición en formato estricto `DD-MM-YYYY`) e `imp` (Importe total con punto como separador decimal).
*   **Gestión de Errores/Anulaciones**: El sistema debe contemplar de forma nativa que los flujos de `RegistroFacturacionAlta` y `RegistroFacturacionAnulacion` son entidades independientes pero comparten el mismo hilo conductor de histórico (el campo `hash_anterior` de una anulación apunta al hash de la factura de alta precedente, y la siguiente factura de alta apuntará al hash generado por esa anulación).

---

## 4. REQUISITOS EN LA CAPA VISUAL (PDF / INTERFAZ)
El módulo de generación de facturas (impresas o PDF generados mediante librerías como `ReportLab` o `WeasyPrint`) debe incluir de manera obligatoria:
1.  **Distintivo Textual**: La cadena literal **"VERI*FACTU"** o **"Factura verificable en la sede electrónica de la AEAT"**.
2.  **Código QR**: Un código QR dinámico generado con la librería `qrcode` que apunte a la URL de cotejo oficial parametrizada descrita en el apartado 3.5.

---

## 5. REQUISITOS LEGALES DE ENTREGA: DECLARACIÓN RESPONSABLE
*   **Obligación del software**: Debe incluir una sección visible en el sistema (ej. "Ajustes > Certificaciones" o "Acerca de") que permita al usuario final descargar un documento PDF firmado por el fabricante del software.
*   **Contenido del documento**: Identificación legal del desarrollador, nombre de la aplicación, número de versión específico comercializado y la declaración formal explícita de cumplimiento del artículo 29.2.j de la Ley General Tributaria y el Real Decreto 1007/2023.

---

## 6. INSTRUCCIONES ADICIONALES PARA EL LLM
*   Prioriza siempre el uso de **FastAPI** como framework API por su naturaleza asíncrona nativa si se requiere arquitectura Cloud/Web.
*   Toda propuesta de base de datos relacional (ej. PostgreSQL con SQLAlchemy) debe incluir mecanismos o recomendaciones de restricción estricta de accesos (como *triggers* que bloqueen `UPDATE` o `DELETE`) para asegurar la inalterabilidad absoluta de las tablas de facturación.
*   No omitas bajo ningún concepto la gestión estricta de errores en los bloques de red (peticiones SOAP/REST) para alimentar correctamente la cola de reintentos Offline.
