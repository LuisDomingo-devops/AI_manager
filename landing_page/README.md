# Alfonso Landing Page V2

Esta carpeta contiene una versión rediseñada de la landing de Alfonso.

## Cambios principales

- Reposicionamiento: de "producto IA/cyberpunk" a "asistente fiscal y administrativo".
- Hero orientado a beneficio y conversión.
- Dashboard visual del producto.
- Flujo "Alfonso hace / tú decides".
- Secciones de público objetivo, funcionalidades y seguridad.
- FAQ con lenguaje prudente sobre cumplimiento y privacidad.
- Calculadora de tiempo/valor.
- Demo local de subida de archivos sin afirmar OCR real.
- Waitlist preparada para conectar con backend.
- Responsive y menú móvil.
- Reducción de claims absolutos como "privacidad absoluta", "100% privado" o "cumplimiento definitivo".

## Instalación

Coloca los tres archivos:

- index.html
- styles.css
- app.js

en `landing_page/`.

No requiere build system: puede abrirse directamente en un navegador.

## Antes de producción

1. Conectar el formulario de waitlist al backend/CRM.
2. Sustituir el dashboard mockup por capturas reales del producto.
3. Validar jurídicamente todas las afirmaciones sobre privacidad, Veri*Factu*, certificados y presentación fiscal.
4. Añadir política de privacidad, cookies y textos legales adecuados.
5. Medir conversiones con analytics.
6. Sustituir la demo local por una demo real si el backend ya permite procesar facturas.

## V2.1 — Iconografía

Se eliminaron los emojis de la interfaz y se sustituyeron por iconos SVG monocromos integrados mediante CSS masks. No requiere librerías externas de iconos y mantiene una estética SaaS/B2B profesional.

## V2.2 — Calculadora de tiempo y coste

La sección «Recupera tu tiempo» usa una referencia de 120 €/mes para una gestoría media-alta y permite estimar dinámicamente el valor mensual y anual del tiempo recuperado según las horas administrativas y el valor/hora introducidos por el visitante. Las referencias de mercado consultadas se mantienen en la propia página.

## V2.3 — Calculadora comercial de ROI

La calculadora incorpora una referencia de gestoría de 120 €/mes y una referencia comercial provisional de Alfonso de 39 €/mes. El resultado combina el ahorro directo frente a esa gestoría de referencia con el valor de las horas administrativas recuperadas. El precio de 39 €/mes está señalado como provisional y debe sustituirse por el pricing definitivo antes de publicar la landing.

## V2.4 — Referencia de gestoría dentro de la calculadora

Se añade dentro de `section#calculadora` > `.calculator` un cuadro visual con una referencia de mercado de **120 €/mes**, sin convertirla en un precio oficial de Alfonso. Se elimina la sección de calculadora duplicada añadida en versiones anteriores.

## V2.5 — Gestoría integrada en el cálculo

El coste de gestoría ya no es un dato decorativo: el visitante introduce lo que paga actualmente y ese importe participa directamente en el cálculo del ahorro mensual y anual. El cuadro tiene contraste visual reforzado y el valor es editable.

## V3.0 — Calculadora premium

Rediseño visual de la calculadora de tiempo, manteniendo únicamente horas mensuales y valor por hora.

## V3.1 — Escala y contraste

Se reduce ligeramente el tamaño general de la calculadora y se aumenta el contraste de los textos para mejorar legibilidad sobre el fondo oscuro.

## V3.2 — Contraste alto

Se aumenta de forma significativa el contraste entre fondos y textos de la calculadora. Se evita el blanco sobre gris claro y se utilizan fondos más oscuros, textos secundarios más luminosos y divisores más definidos.
