# Implementation Plan: Saneamiento y Desacoplamiento de ApprovalService (Spec 002)

**Branch**: `002-approval-service` | **Date**: 2026-09-28 | **Spec**: [spec.md](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/specs/002-approval-service/spec.md)

---

## 1. Summary

Erradicar el mock global `autouse=True` de `ApprovalService` en `tests/conftest.py`, corregir las 15 invocaciones de método de clase inválidas en `payroll_tools.py` y `aeat_automation_tools.py`, e implementar una batería TDD estricta (unitario, integración y QA) para validar los flujos de rechazo y timeout de la gobernanza humana (Human-in-the-Loop / Out-of-Band).

---

## 2. Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, Pydantic v2, Pytest, Pytest-Asyncio, asyncio  
**Architecture Layer**: Application Tools (`app/tools/server/`) & Domain Services (`app/domain/services/`)  
**Testing Framework**: Pytest con fixtures nombrados y aserciones deterministas sobre estado y base de datos  

---

## 3. Constitution & Discovery Rules Check

| Regla Constitucional / Discovery | Estado | Justificación |
|---|---|---|
| **I. Idioma Español** | ✅ PASS | Documentación, nombres de tests y logs en castellano. |
| **II. TDD Estricto** | ✅ PASS | Se redactarán primero los tests que fallen evidenciando el error real al remover el mock global. |
| **III. Cobertura Triple** | ✅ PASS | Unitario (`test_approval_service_contracts.py`), Integración (`test_approval_rejection_workflows.py`) y QA (`test_approval_governance_suite.py`). |
| **IV. Preservación y Logs** | ✅ PASS | La suite completa se ejecutará registrando el log correspondiente en `tests/logs/spec002/`. |
| **V. No maquillar tests** | ✅ PASS | Se erradica el mock global que devuelve `True` a ciegas para evidenciar y testear los caminos de rechazo real. |

---

## 4. Fases de Ejecución

### Fase 1: Setup y Creación de Tests TDD (Red)
1. Crear carpeta de logs en `tests/logs/spec002/`.
2. Crear `tests/backend/unit/test_approval_service_contracts.py`:
   - Validar que `ApprovalService.request_approval` falla o requiere instancia si no se usa método de clase.
   - Validar que `approval_service.resolve_approval` resuelve futuros con `True`, `False` y timeout.
3. Crear `tests/backend/integration/test_approval_rejection_workflows.py`:
   - Validar que cuando el usuario rechaza (`approved=False`), `create_employee_tool` y `generate_model_303_draft_tool` devuelven `status: "pending_confirmation"` y no modifican base de datos.
4. Crear `tests/backend/qa/test_approval_governance_suite.py`:
   - Validar el gobierno integral de acciones irreversibles (borrado de clientes, nóminas y declaraciones AEAT).

### Fase 2: Implementación en Código de Producción (Green)
1. En `app/domain/services/approval_service.py`:
   - Añadir soporte seguro a nivel de clase para que `ApprovalService.request_approval(...)` delegue de forma transparente a la instancia canónica `approval_service`, previniendo errores de `missing self`.
2. En `app/tools/server/payroll_tools.py`:
   - Actualizar importaciones e invocar `approval_service.request_approval(...)` en las 3 funciones laborales.
3. En `app/tools/server/aeat_automation_tools.py`:
   - Actualizar importaciones e invocar `approval_service.request_approval(...)` en las 12 herramientas tributarias.
4. En `tests/conftest.py`:
   - Eliminar `autouse=True` de `mock_approval_service` y ofrecer fixtures explícitos `mock_approval_granted`, `mock_approval_rejected`.
   - Ajustar los tests que dependían del mock global para que soliciten `mock_approval_granted` explícitamente.

### Fase 3: Verificación y Cierre
1. Ejecutar las nuevas suites de prueba de la Spec 002.
2. Ejecutar la suite completa del repositorio y volcar en `pytest-logs.txt`.
3. Validar ausencia de regresiones.
