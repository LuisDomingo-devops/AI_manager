# Implementation Plan: Saneamiento Global de Excepciones y Erradicación de "AI Slop" (Spec 019)

**Branch**: `019-saneamiento-excepciones-ai-slop` | **Date**: 2026-09-28 | **Spec**: [spec.md](file:///c:/Users/luisd/Desktop/Alfonso_Autonomo/specs/019-saneamiento-excepciones-ai-slop/spec.md)

---

## 1. Summary

Erradicar de manera sistemática y bajo metodología TDD estricta el patrón de código defensivo autogenerado ("AI Slop") consistente en:
```python
except Exception:
    from app.utils.logger import error_logger
    error_logger.warning("Excepción interceptada:", exc_info=True)
```
auditado en **44 puntos exactos** a lo largo de **16 archivos** del núcleo de `app/`, junto con **51 importaciones locales tardías** de `error_logger`. 

El enfoque técnico consiste en:
1. Reemplazar la captura ciega de `Exception` por excepciones tipadas de infraestructura, base de datos (`sqlite3.Error`), criptografía y llamadas externas (`httpx.HTTPError`).
2. Garantizar que fallos en registros de auditoría de facturación y generación de correlativos emitan alertas severas o propaguen el error sin corromper la trazabilidad de la Ley Antifraude / Veri*Factu.
3. Centralizar las importaciones de logging a nivel de módulo, resolviendo dependencias circulares.
4. Diseñar pruebas unitarias, de integración y QA con aserciones estrictas sobre los caminos de fallo para cada subsistema.

---

## 2. Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, Pydantic v2, Pytest, Pytest-Asyncio, SQLite3, HTTPX  
**Storage**: SQLite local multi-tenant (`AuditLedgerService`, `InvoiceRepository`, `CalendarDB`)  
**Testing**: `uv run pytest` (Suite completa de 520+ tests)  
**Target Platform**: Windows 11 / Linux (Multiplataforma)  
**Project Type**: Backend SaaS modular con agentes especializados y orquestador determinista  
**Constraints**:
- **Metodología TDD obligatoria**: Diseñar los tests de fallo y verificación antes de modificar el código de producción.
- **Cobertura triple**: Cada User Story debe incluir tests unitarios, de integración y QA.
- **0 dependencias de red en tests**: Todo mockeado y aislado localmente.
- **Registro de logs**: Guardar los logs de ejecución tras cada batería de pruebas en `tests/logs/spec019/`.
- **Integridad de la suite**: Preservar los 512 tests existentes en verde al 100%.

---

## 3. Constitution Check

*GATE: Evaluación frente a la Constitución del Proyecto (AI_Manager Constitution v1.0.0).*

| Principio Constitucional | Estado | Justificación / Mecanismo de Cumplimiento |
|---|---|---|
| **I. Desarrollo en Español** | ✅ PASS | Todo el plan, especificación, comentarios, logs y documentación están redactados estrictamente en castellano. |
| **II. TDD Estricto** | ✅ PASS | Se redactarán primero los tests que reproduzcan y validen el manejo de fallos para cada grupo de archivos antes de tocar el código productivo. |
| **III. Cobertura Completa** | ✅ PASS | Cada una de las 4 User Stories incorporará tests unitarios, de integración y QA dedicados. |
| **IV. Ejecución Continua y Registro** | ✅ PASS | Se ejecutará la suite completa y se archivarán los logs en `tests_execution_019.log` y en `tests/logs/spec019/`. |
| **V. Navegador Firefox** | ✅ PASS | No aplica a backend/CLI, pero si se interactúa con interfaz web se empleará Firefox exclusivamente. |

---

## 4. Project Structure & Artifacts

### Documentación de la Feature
```text
specs/019-saneamiento-excepciones-ai-slop/
├── spec.md              # Especificación funcional y de auditoría
├── plan.md              # Este plan de implementación
├── research.md          # Decisiones arquitectónicas y taxonomía de excepciones
├── data-model.md        # Diagramas de jerarquía de excepciones y contratos
└── quickstart.md        # Guía de validación y comandos paso a paso
```

### Código Fuente y Áreas Afectadas (16 Archivos)

```text
app/
├── tools/server/
│   └── billing_tools.py               (16 casos: facturación, presupuestos, auditoría)
├── infrastructure/
│   ├── database/
│   │   ├── repositories/invoice_repository.py (4 casos: persistencia facturas)
│   │   ├── calendar_db.py              (1 caso: persistencia calendario)
│   │   └── memory/vector_memory.py     (1 caso: memoria vectorial)
│   └── adapters/
│       ├── bank_providers.py           (4 casos: pasarelas bancarias)
│       ├── tool_registry.py            (1 caso: despacho de tools)
│       ├── llm_client.py               (1 caso: cliente Gemini)
│       └── gmail_sync.py               (1 caso: sincronización Gmail)
├── domain/
│   ├── prompt_generator.py             (2 casos: prompts LLM)
│   └── agents/security/security_agent.py (1 caso: agente ciberseguridad)
├── utils/
│   ├── license_validator.py            (5 casos: hardware fingerprint)
│   ├── logger.py                       (3 casos: logging central)
│   └── paths.py                        (1 caso: resolución rutas SO)
├── api/v1/
│   └── onboarding_router.py            (1 caso: onboarding API)
├── main.py                             (1 caso: decodificación body)
└── config.py                           (1 caso: parsing configuración)
```

---

## 5. Fases de Ejecución TDD

### Phase 1: Setup y Preparación
- Crear directorio de logs de prueba: `tests/logs/spec019/`.
- Verificar baseline: conteo de 44 ocurrencias de `Excepción interceptada` y suite base con 512 tests pasando.

---

### Phase 2: User Story 1 (P1) — Facturación, Presupuestos y Repositorio (20 casos)
*Archivos: `billing_tools.py` (16), `invoice_repository.py` (4)*

1. **Test TDD (Red)**:
   - Crear `tests/backend/unit/test_billing_exceptions_qa.py` forzando fallos de auditoría en `DELETE_CLIENT`, descifrado corrupto en presupuestos y desconexión en inserción de facturas.
   - Verificar que los tests fallan si el código actual silencia silenciosamente la excepción.
2. **Implementación (Green)**:
   - Sustituir los 16 bloques en `billing_tools.py` por captura de `sqlite3.Error`, `CryptoError` / `ValueError` y gestión severa ante fallo de `AuditLedgerService`.
   - Sustituir los 4 bloques en `invoice_repository.py` por captura explícita de `sqlite3.Error` y propagación controlada.
   - Mover los imports de `error_logger` a la cabecera.
3. **Verificación**:
   - Comprobar que los nuevos tests pasan y que los tests existentes de facturación continúan en verde.

---

### Phase 3: User Story 2 (P2) — Seguridad, Licencias y Conectores Bancarios (11 casos)
*Archivos: `license_validator.py` (5), `bank_providers.py` (4), `llm_client.py` (1), `security_agent.py` (1)*

1. **Test TDD (Red)**:
   - Crear `tests/backend/unit/test_security_bank_exceptions.py` simulando claves de registro inaccesibles en Windows, timeout bancario y payload malformado de LLM.
2. **Implementación (Green)**:
   - En `license_validator.py`, tipar las 5 capturas con `(OSError, FileNotFoundError, PermissionError, AttributeError)`.
   - En `bank_providers.py`, tipar con `(httpx.HTTPError, httpx.TimeoutException, KeyError)`.
   - En `llm_client.py` y `security_agent.py`, tipar con errores de proveedor y validación.
   - Eliminar imports inline de logger.
3. **Verificación**:
   - Re-ejecutar tests de licencias y bancos. Guardar log.

---

### Phase 4: User Story 3 (P3) — Infraestructura Auxiliar, DB y Mail (4 casos)
*Archivos: `calendar_db.py` (1), `vector_memory.py` (1), `gmail_sync.py` (1), `tool_registry.py` (1)*

1. **Test TDD (Red)**:
   - Crear `tests/backend/integration/test_aux_infra_exceptions.py` probando caídas de conexión en calendario, fallo en indexación vectorial y error en lectura de correo.
2. **Implementación (Green)**:
   - Reemplazar capturas genéricas por excepciones tipadas de conexión y parsing.
   - Limpiar imports de logger.
3. **Verificación**:
   - Ejecutar suite de infraestructura. Guardar log.

---

### Phase 5: User Story 4 (P4) — Core, Logging, API y Configuración (9 casos)
*Archivos: `paths.py` (1), `logger.py` (3), `main.py` (1), `config.py` (1), `onboarding_router.py` (1), `prompt_generator.py` (2)*

1. **Test TDD (Red)**:
   - Crear `tests/backend/unit/test_core_config_exceptions.py` probando paths inexistentes, JSON malformado en body de FastAPI y config inválida.
2. **Implementación (Green)**:
   - Sustituir bloques por captura explícita de `(IOError, OSError, ValueError, KeyError)`.
   - Asegurar que `logger.py` no sufra dependencias circulares.
3. **Verificación**:
   - Validar suite de utilidades y API. Guardar log.

---

### Phase 6: Validación Final de Toda la Suite del Repositorio (Regla IV)
1. Ejecutar el script de comprobación: verificar que el conteo de `Excepción interceptada:` en `app/` es exactamente **0**.
2. Ejecutar la suite completa de pruebas: `uv run pytest`.
3. Validar que pasan todos los tests (0 fallos).
4. Guardar el log definitivo en `tests_execution_019.log`.
