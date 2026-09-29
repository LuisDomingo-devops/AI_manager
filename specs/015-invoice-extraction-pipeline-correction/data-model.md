# Modelo de Datos (Phase 1)

## Entidades Principales

### `InvoiceSchema` (Esquema de Factura Pydantic)
El esquema principal debe asegurar que las tasas impositivas y las retenciones sigan reglas matemáticas estrictas.

**Campos principales relevantes para esta corrección:**
- `base_amount`: float (Monto base imponible)
- `iva_amount`: float (Monto del IVA)
- `iva_rate`: float (Porcentaje de IVA). **Regla de Validación:** DEBE ser un valor de 0.0 a 100.0. Los valores típicos esperados en España son 4.0, 10.0, 21.0.
- `irpf_amount`: float (Monto de retención)
- `irpf_rate`: float (Porcentaje de IRPF). **Regla de Validación:** DEBE ser un valor de 0.0 a 100.0. Valores típicos 7.0, 15.0, etc.
- `total_amount`: float (Monto total). **Regla de Validación:** Lógicamente, `total = base + iva - irpf`.
- `requires_manual_confirmation`: bool (Flag para marcar la factura para revisión humana si la extracción tiene dudas).

### Flujo de Estado y Validación
1. El LLM extrae los valores crudos.
2. `TaxParserService` (u otro componente) recibe el output crudo.
3. Se aplican transformaciones/sanitizaciones antes de instanciar `InvoiceSchema`.
    - Si el LLM pone un valor > 100 en `iva_rate`, se intenta inferir que fue un error donde se confundió con `iva_amount`. Si el `base_amount` está presente y `iva_rate_erroneo` = `iva_amount`, se intercambian o se calcula el porcentaje.
    - Si la matemática está severamente rota y es ininteligible, se setean los valores a los más seguros y se activa `requires_manual_confirmation = True`.
4. Si se instancia `InvoiceSchema` y falla, la excepción de Pydantic debe ser capturada y manejada, convirtiendo la respuesta en una factura válida pero incompleta o dudosa con `requires_manual_confirmation = True`, en lugar de propagar la excepción Pydantic cruda.
