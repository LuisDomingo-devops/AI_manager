# Tasks: Saneamiento Global de Excepciones y Erradicación de "AI Slop" (Spec 019)

**Objetivo**: Erradicar el patrón de código defensivo autogenerado ("AI Slop") consistente en 44 bloques idénticos de captura genérica de excepciones y 51 imports inline de `error_logger` en 16 archivos de `app/`, aplicando la metodología estricta de Test-Driven Development (TDD) con tests unitarios, de integración y QA.

**Metodología TDD**:
1. **Red**: Escribir y ejecutar el test de fallo forzando el camino de excepción; comprobar que falla ante la captura silenciosa o que valida el comportamiento tipado esperado.
2. **Green**: Sustituir el bloque por excepciones tipadas (`sqlite3.Error`, `CryptoError`, `OSError`, etc.) y mover el import de logger a nivel de módulo.
3. **Refactor / Verify**: Re-ejecutar el test individual, verificar que pasa al 100% y guardar el log en `tests/logs/spec019/`.

---

## Phase 1: Setup y Preparación

**Propósito**: Preparación de infraestructura de testing, carpetas de logging y medición de la línea base.

- [x] T001 Crear el directorio de logs de ejecución TDD en `tests/logs/spec019/`
- [x] T002 Ejecutar script de verificación baseline y registrar las 44 ocurrencias iniciales en `tests/logs/spec019/baseline_count.log`
- [x] T003 [P] Crear módulo de excepciones base tipadas si se requiere en `app/domain/exceptions.py`

---

## Phase 2: User Story 1 (P1) — Facturación, Presupuestos y Repositorio de Facturas (20 Casos)

**Meta**: Saneamiento de las 16 ocurrencias en `billing_tools.py` y las 4 en `invoice_repository.py`. Garantizar que fallos de auditoría no se silencien y que el descifrado corrupto no desvirtúe los correlativos.

**Criterio de Prueba Independiente**: Los tests en `tests/backend/unit/test_billing_exceptions.py` y `tests/backend/integration/test_invoice_repo_resilience.py` deben validar la captura tipada y el tratamiento de errores sin swallow silencioso.

### Tests TDD (Red)
- [x] T004 [P] [US1] Crear test unitario forzando fallo en `AuditLedgerService.log_audit_event` y descifrado de presupuestos en `tests/backend/unit/test_billing_exceptions.py`
- [x] T005 [P] [US1] Crear test de integración forzando errores de SQLite en inserción/consulta de facturas en `tests/backend/integration/test_invoice_repo_resilience.py`
- [x] T006 [P] [US1] Crear test de QA de integridad regulatoria en facturación y auditoría en `tests/backend/qa/test_billing_audit_integrity_suite.py`
- [x] T007 [US1] Ejecutar los tests T004-T006 en modo Red y registrar el log en `tests/logs/spec019/us1_red.log`

### Implementación TDD (Green)
- [x] T008 [US1] Mover imports de `error_logger` a la cabecera en `app/tools/server/billing_tools.py`
- [x] T009 [US1] Reemplazar los 16 bloques `except Exception:` por excepciones tipadas (`sqlite3.Error`, `CryptoError`, `ValueError`) y alertas severas de auditoría en `app/tools/server/billing_tools.py`
- [x] T010 [US1] Mover imports de `error_logger` a la cabecera en `app/infrastructure/database/repositories/invoice_repository.py`
- [x] T011 [US1] Reemplazar los 4 bloques `except Exception:` por captura explícita de `sqlite3.Error` en `app/infrastructure/database/repositories/invoice_repository.py`

### Verificación y Logs (TDD)
- [x] T012 [US1] Re-ejecutar `tests/backend/unit/test_billing_exceptions.py`, `test_invoice_repo_resilience.py` y suite de facturación existente, guardando log en `tests/logs/spec019/us1_green.log`

---

## Phase 3: User Story 2 (P2) — Seguridad, Licencias y Pasarelas Bancarias (11 Casos)

**Meta**: Saneamiento de las 5 ocurrencias en `license_validator.py`, 4 en `bank_providers.py`, 1 en `llm_client.py` y 1 en `security_agent.py`.

**Criterio de Prueba Independiente**: Los tests en `tests/backend/unit/test_license_validator_resilience.py` y `tests/backend/integration/test_bank_providers_resilience.py` deben pasar al 100%.

### Tests TDD (Red)
- [x] T013 [P] [US2] Crear test unitario simulando errores de acceso al registro de Windows y fallbacks de hardware en `tests/backend/unit/test_license_validator_resilience.py`
- [x] T014 [P] [US2] Crear test de integración simulando fallos de red HTTP y parsing en pasarelas bancarias en `tests/backend/integration/test_bank_providers_resilience.py`
- [x] T015 [P] [US2] Crear test de QA de robustez del agente de ciberseguridad y cliente LLM ante respuestas malformadas en `tests/backend/qa/test_security_agent_resilience_suite.py`
- [x] T016 [US2] Ejecutar los tests T013-T015 en modo Red y registrar el log en `tests/logs/spec019/us2_red.log`

### Implementación TDD (Green)
- [x] T017 [US2] Reemplazar las 5 capturas en `app/utils/license_validator.py` por captura específica de `(OSError, FileNotFoundError, PermissionError, AttributeError)` y limpiar imports inline
- [x] T018 [US2] Reemplazar las 4 capturas en `app/infrastructure/adapters/bank_providers.py` por `(httpx.HTTPError, httpx.TimeoutException, KeyError)` y limpiar imports inline
- [x] T019 [US2] Reemplazar el bloque genérico en `app/infrastructure/adapters/llm_client.py` por manejo tipado de errores de comunicación y limpiar imports inline
- [x] T020 [US2] Reemplazar el bloque genérico en `app/domain/agents/security/security_agent.py` por excepciones tipadas de validación y limpiar imports inline

### Verificación y Logs (TDD)
- [x] T021 [US2] Re-ejecutar `test_license_validator_resilience.py`, `test_bank_providers_resilience.py` y `test_security_agent_resilience_suite.py`, guardando log en `tests/logs/spec019/us2_green.log`

---

## Phase 4: User Story 3 (P3) — Infraestructura Auxiliar, Base de Datos y Mail (4 Casos)

**Meta**: Saneamiento de las 4 ocurrencias en `calendar_db.py` (1), `vector_memory.py` (1), `gmail_sync.py` (1) y `tool_registry.py` (1).

**Criterio de Prueba Independiente**: Los tests en `tests/backend/integration/test_aux_infra_resilience.py` deben validar la gestión explícita de caídas de persistencia y parsing de correo.

### Tests TDD (Red)
- [x] T022 [P] [US3] Crear test unitario/integración simulando errores de conexión en base de datos de calendario y vector memory en `tests/backend/integration/test_aux_infra_resilience.py`
- [x] T023 [P] [US3] Crear test de QA para despacho de tools y sincronización de correo ante errores inesperados en `tests/backend/qa/test_tool_registry_resilience_suite.py` y `test_gmail_sync_resilience.py`
- [x] T024 [US3] Ejecutar los tests T022-T023 en modo Red y registrar el log en `tests/logs/spec019/us3_red.log`

### Implementación TDD (Green)
- [x] T025 [US3] Sustituir el bloque genérico por `sqlite3.Error` en `app/infrastructure/database/calendar_db.py`
- [x] T026 [US3] Sustituir el bloque genérico por errores de serialización/vectorial en `app/infrastructure/database/memory/vector_memory.py`
- [x] T027 [US3] Sustituir el bloque genérico por errores de API/deserialización en `app/infrastructure/adapters/gmail_sync.py`
- [x] T028 [US3] Sustituir el bloque genérico por `(KeyError, ValueError, AttributeError)` en `app/infrastructure/adapters/tool_registry.py`
- [x] T029 [US3] Mover imports de `error_logger` a la cabecera en los 4 módulos de infraestructura

### Verificación y Logs (TDD)
- [x] T030 [US3] Re-ejecutar `test_aux_infra_resilience.py`, `test_gmail_sync_resilience.py` y `test_tool_registry_resilience_suite.py`, guardando log en `tests/logs/spec019/us3_green.log`

---

## Phase 5: User Story 4 (P4) — Core, Logging, API y Configuración (9 Casos)

**Meta**: Saneamiento de las ocurrencias en `paths.py` (1), `logger.py` (3), `config.py` (1), `onboarding_router.py` (1) y `prompt_generator.py` (2).

**Criterio de Prueba Independiente**: Los tests en `tests/backend/unit/test_paths_resilience.py`, `tests/backend/unit/test_logger_resilience.py`, `tests/backend/integration/test_config_onboarding_resilience.py` y `tests/backend/qa/test_prompts_core_suite.py` deben pasar al 100%.

### Tests TDD (Red)
- [x] T031 [P] [US4] Crear test unitario para resolución de rutas en `tests/backend/unit/test_paths_resilience.py`
- [x] T032 [P] [US4] Crear test unitario verificando la robustez de handlers de logging y formateadores en `tests/backend/unit/test_logger_resilience.py`
- [x] T033 [P] [US4] Crear test de integración para carga de configuración y router de onboarding en `tests/backend/integration/test_config_onboarding_resilience.py`
- [x] T034 [US4] Crear test de QA de robustez del generador de prompts y contexto en `tests/backend/qa/test_prompts_core_suite.py` y registrar el log Red en `tests/logs/spec019/us4_red.log`

### Implementación TDD (Green)
- [x] T035 [US4] Sustituir captura en `app/utils/paths.py` por `(OSError, ValueError)` y mover import a cabecera
- [x] T036 [US4] Sustituir capturas en `app/utils/logger.py` por manejo resiliente de I/O y formato sin recursión
- [x] T037 [US4] Sustituir captura en `app/config.py` por `(OSError, UnicodeDecodeError, ValueError)`
- [x] T038 [US4] Sustituir captura en `app/api/v1/onboarding_router.py` por excepciones tipadas de persistencia SQLite
- [x] T039 [US4] Sustituir capturas en `app/domain/prompt_generator.py` por `(OSError, json.JSONDecodeError, UnicodeDecodeError)`
- [x] T040 [US4] Validar ausencia de efectos colaterales en el arranque y rutas core

### Verificación y Logs (TDD)
- [x] T041 [US4] Re-ejecutar tests de US4 y suite completa, guardando logs en `tests/logs/spec019/us4_green.log` y `tests/logs/spec019/full_suite_us4.log`

---

## Phase 6: Validación Final de Toda la Suite del Repositorio (Regla IV)

**Propósito**: Verificar la erradicación total del patrón a nivel de repositorio y la preservación del 100% de la suite de pruebas.

- [x] T042 Ejecutar script de verificación y certificar que el conteo de `Excepción interceptada:` en `app/` es exactamente **0**
- [x] T043 Ejecutar script de verificación y certificar que las importaciones inline de `error_logger` en bloques de excepción son exactamente **0**
- [x] T044 Ejecutar la suite completa de pruebas del repositorio (`pytest -c tests/pytest.ini`) y registrar la salida completa en `tests/logs/spec019/final_full_suite.log`
- [x] T045 Verificar que los 547 tests pasan limpiamente (0 fallos globales)
- [x] T046 Generar el informe de cierre y entrega formal de la Spec 019
