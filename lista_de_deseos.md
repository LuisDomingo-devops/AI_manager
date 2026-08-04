# Lista de Deseos (Wishlist) - Alfonso Autónomo

Este documento recopila las ideas, propuestas y características futuras que aportan gran valor al asistente, pero que se desarrollarán en fases posteriores para mantener el foco en el núcleo del producto (Core Local + Verifactu).

---

## 1. Solución Local de Documentos con Edición en Vivo
*   **Descripción:** Visualización e interacción con los ingresos, gastos y facturas del autónomo sin depender de servicios en la nube como Google Sheets.
*   **Detalles Técnicos:**
    *   Interfaz web local reactiva en el frontend (`client/`) con tablas interactivas de estilo Notion o Airtable.
    *   Sincronización en vivo mediante WebSockets/HTTP con el backend local (FastAPI + SQLite).
    *   Exportación y actualización asíncrona automática en archivos físicos Excel (`.xlsx`) en el disco duro del usuario para mantener la propiedad y portabilidad del dato.

---

## 2. Guardián de la AEAT y Seguridad Social (Extensión de Navegador)
*   **Descripción:** Un copiloto web interactivo que guía al usuario y evita pasos en falso en los portales oficiales de Hacienda y la Seguridad Social.
*   **Detalles Técnicos:**
    *   Extensión web (Manifest V3) conectada por WebSockets al servidor local de Alfonso.
    *   **Guía Visual (GPS):** Resaltado dinámico en pantalla de botones y campos para usuarios perdidos en el portal de la Seguridad Social o AEAT.
    *   **Auto-relleno Seguro:** Inyección controlada de datos de la base de datos local en los formularios web de impuestos (Modelos 303, 130, etc.).
    *   **Watchdog (Filtro Antierrores):** Interceptación del botón de firma/envío nativo (`event.preventDefault()`). El botón se bloquea hasta que el usuario dé el visto bueno final en un banner de revisión de Alfonso, requiriendo su certificado digital físico para el envío.

---

## 3. Lector del BOE e Implementación de Cambios Fiscales en Vivo
*   **Descripción:** Automatización del análisis legislativo español para que Alfonso actualice de forma autónoma sus reglas de cálculo en función de las leyes publicadas.
*   **Detalles Técnicos:**
    *   Suscripción/ingesta automática del Boletín Oficial del Estado (BOE) cada vez que se publique una nueva edición.
    *   Procesamiento del boletín mediante LLM con RAG especializado en leyes fiscales para identificar cambios que afecten a autónomos (tipos de IVA, deducciones, tramos de IRPF, bases de cotización).
    *   Actualización dinámica de la base de reglas del motor local de Alfonso para aplicar la nueva fiscalidad del usuario sin requerir actualizaciones manuales de software complejas.
