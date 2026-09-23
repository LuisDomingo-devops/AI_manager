# SPEC 2 — Verificación real de Veri*Factu / AEAT

## Problem
La integración actual y los tests presentan varias carencias críticas y solapamientos que otorgan falsos positivos (TST-01). En la suite GUI se utiliza un mock global masivo de `requests` que absorbe cualquier error de red. Por otro lado, no existen pruebas de contrato, y no existe garantía automatizada de la conexión con el Sandbox de la AEAT.

## Evidence
- **TST-01:** `tests/client/qa/test_gui_qa_suite.py` líneas 56-59 (Mock global indiscriminado de `requests`).
- **UNVERIFIED:** XMLDSig (Firma criptográfica).
- **UNVERIFIED:** AEAT Sandbox Connection E2E.

## Scope
- Suite QA de cliente GUI.
- Lógica de emisión XML a AEAT.
- Contract Tests HTTP.

## Non-goals
- Validar asumiendo que el XSD correcto equivale a un XMLDSig correcto.
- Mezclar el test de Sandbox en la suite unitaria estándar.
- Incluir certificados reales de FNMT en Git, código fuente o fixtures estáticas.

## Current behavior
- Todos los tests QA del cliente simulan 200 OK con JSON vacío genérico, enmascarando cualquier ruptura en la comunicación cliente-servidor real.
- XMLDSig no posee evidencia automatizada demostrable.

## Expected behavior
Se segmenta la validación en capas estrictas:

- **A. Tests Unitarios (Sin Red):** Verifican exclusivamente la lógica del código y la conformación teórica del XML/XSD en memoria. Sin acceso a internet.
- **B. Contract Tests:** Verifican que la comunicación cliente-servidor cumple el esquema HTTP esperado (URL, métodos, headers, payload json, respuestas y errores), sin usar mocks globales indiscriminados. El cliente envía, y el test valida la petición sin salir a la AEAT.
- **C. AEAT Sandbox E2E:** Prueba explícita (`opt-in`) contra la AEAT real. Solo corre si existen las credenciales/certificados (ej. flag `AEAT_SANDBOX_ENABLED=true` u homólogo en el entorno). Si falta el entorno, se descarta (skip) sin romper la suite unitaria.
- **D. Verificación XMLDSig:** Queda documentada como UNVERIFIED hasta poseer pruebas criptográficas aisladas o confirmación por el Sandbox de que el hash firmado es correcto.

## Requirements
- **3A. Eliminación de Mock Global GUI:** Remover el `patch("requests.Session.get")` en `test_gui_qa_suite.py`. Implementar un test server local o adaptador que valide endpoints reales del backend. No aceptar `{"status": "ok"}` genéricos.
- **3B. Contract Tests:** Escribir tests que validen estrictamente el contrato HTTP (rutas, errores, payloads).
- **3C. AEAT Sandbox E2E:** Escribir test aislado contra `prewww10.aeat.es`. Requisito: debe inyectar secretos mediante variables locales del corredor/CI, nunca en el repositorio.

## Invariants
- Los tests unitarios y de contrato NO deben depender de Internet ni de la AEAT.
- La ausencia de credenciales de la AEAT NO puede romper la ejecución de los tests unitarios.
- XMLDSig NO se asume como validado simplemente porque se valide el formato XSD.

## Acceptance criteria
- `pytest tests/client/qa/` se ejecuta con un servidor de pruebas controlado (ej. `pytest-httpserver`) validando payload real en lugar de interceptar `requests`.
- Existen tests de contrato que asertan endpoints específicos (headers y status code correctos).
- El test de Sandbox de la AEAT solo arranca si el flag/entorno está activo.

## Required tests
1. Tests QA de GUI apuntando a servidor controlado local y evaluando las regresiones sin ocultarlas.
2. Contract Tests validando schemas JSON.
3. Test E2E de Sandbox AEAT asertando HTTP 200/SOAP Response.

## Dependencies
- Primero se inspeccionarán las dependencias y utilidades de testing existentes.
- Se determinará si ya existe una alternativa adecuada para levantar un servidor HTTP local/controlado.
- Solo si no existe una alternativa adecuada se propondrá `pytest-httpserver`.
- No instalar ninguna dependencia durante esta fase documental.

## Risks
- Al eliminar el mock global, pueden aparecer errores reales en la app cliente que antes estaban ocultos. Serán tratados como Bugs Confirmados, Defectos de Test o Regresiones, y documentados.

## Open questions
- ¿Qué herramienta se usará finalmente para levantar el backend en los QA del cliente si no se aprueba `pytest-httpserver`?
- ¿Cómo se proveerán los certificados de la FNMT en el pipeline E2E?
