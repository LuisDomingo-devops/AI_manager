# Quickstart: Domain Error Contract

## Purpose
This guide verifies that when a tool encounters a validation error, it does not crash or leak technical data (like Pydantic exceptions) to the user, but instead pauses the workflow and asks a natural question.

## Prerequisites
- El entorno de Python debe estar configurado.
- El proyecto debe tener los tests instalados (`uv run pytest`).

## Validation Scenario 1: Shielding Users from Technical Errors

**Paso 1:** Preparar un script de prueba rápida o ejecutar el test de integración destinado a esto.
```bash
uv run pytest tests/backend/integration/test_domain_error_ux.py::test_shielding_validation_errors -v
```

**Paso 2:** Verificar el resultado.
- **Expected Outcome**: El test inyecta una factura corrupta. La aserción comprueba que la respuesta al usuario es algo como "No he podido procesar el campo X", y asegura que "ValidationError" no está en el string devuelto al LLM o al usuario.

## Validation Scenario 2: Workflow Pausing

**Paso 1:** Ejecutar la prueba de pausa de flujo de trabajo.
```bash
uv run pytest tests/backend/integration/test_domain_error_ux.py::test_workflow_pausing -v
```

**Paso 2:** Verificar el resultado.
- **Expected Outcome**: Al detectar `needs_user_validation`, la ejecución devuelve el control emitiendo una interrupción/clarificación (ej. `confirmation_required`), impidiendo que avance a la siguiente tarea hasta que se provea la corrección.
