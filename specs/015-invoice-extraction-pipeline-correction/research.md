# Investigación y Resoluciones Técnicas (Phase 0)

## Análisis del Bug (P-06 y P-03)
- **Problema de Regresión (P-06)**: El pipeline de extracción asigna valores monetarios erróneos (por ejemplo, `503.47`) a los campos porcentuales como `iva_rate`.
- **Excepciones Filtradas (P-03)**: El fallo de validación provocado por datos erróneos extraídos del LLM lanza una `ValidationError` cruda al Orchestrator que no se maneja, causando una mala UX (technical exception leakage).

## Resoluciones (Technical Context)

### ¿Cómo manejar la inferencia de valores porcentuales (iva_rate) y montos (iva_amount)?
- **Decision**: Mantener una validación rígida en `InvoiceSchema` de que `iva_rate` debe estar entre 0.0 y 100.0, y encapsular la captura de errores en `TaxParserService`.
- **Rationale**: No aflojar la rigidez del modelo de datos de `InvoiceSchema`. La lógica de limpieza pertenece al servicio. Si la predicción falla lógicamente y no se puede reparar por deducción matemática de la base/total, se marca con `requires_manual_confirmation = True`.
- **Alternatives considered**: Relajar `InvoiceSchema` para usar campos `str` o usar márgenes más amplios (rechazado por violar la restricción FR-005).

### ¿Cómo manejar el formateo mixto de texto?
- **Decision**: Procesar previamente la cadena de texto con limpieza explícita de caracteres monetarios (`€`, `EUR`, `\$`) antes de asignar valores, priorizando la extracción contextual de `iva_amount` vs `iva_rate` en el prompt, y usar fallback matemático.
- **Rationale**: El LLM a veces es vago y asigna el monto al rate (ej: `IVA 503.47 EUR`). El prompt debe ser más estricto y la capa de sanitización debe comprobar la congruencia (`base * (iva_rate/100) ≈ iva_amount`).

### Resolución de "NEEDS CLARIFICATION"
- Todas las clarificaciones de la fase de planning respecto al lenguaje, dependencias y reglas de error han sido resueltas alineándose al stack existente y a las restricciones descritas. No hay incógnitas bloqueantes en cuanto a dependencias o infraestructura externa.
