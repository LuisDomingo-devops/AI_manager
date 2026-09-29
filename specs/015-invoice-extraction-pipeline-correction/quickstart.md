# Guía de Validación Rápida (Quickstart)

Esta guía describe cómo verificar de manera independiente que la corrección del pipeline de facturas se ha implementado con éxito, sin necesidad de arrancar el frontend completo.

## Prerrequisitos
- Entorno virtual de Python activo.
- Módulo `pytest` instalado.

## Ejecución de Casos de Validación (TDD)

El mecanismo principal para validar esta feature es la suite de tests unitarios/integración.

### Comando para ejecutar la suite de facturas:
```bash
uv run pytest tests/unit/test_tax_parser_service.py -v
```

### Resultados Esperados

1. **Test de Formato Mixto**:
   Deberá existir un test que inyecte un texto con formatos mixtos ("IVA = 21%, base=34,51, total 41.76") en la extracción de la factura. El parser deberá devolver un objeto donde `iva_rate = 21.0` y `iva_amount = 7.25`.

2. **Test de Regresión de Error Monetario (P-06)**:
   Se evaluará un escenario donde el LLM pueda confundirse (simulado o testeado contra una función de parseo que reciba el input bruto donde el LLM puso `503.47` como tasa). El test debe afirmar (assert) que el valor NO termina en `iva_rate` provocando error.

3. **Test de Fallback (P-03)**:
   Se evaluará que ante una inyección de datos irrecuperables en el LLM/extracción, la función devuelve un objeto con `requires_manual_confirmation=True` en lugar de propagar la excepción `ValidationError` que detiene la ejecución.
