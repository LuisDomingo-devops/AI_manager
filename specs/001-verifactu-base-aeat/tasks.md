# Tasks: Consolidación Arquitectura y Conformidad VeriFactu (AEAT)

**Feature**: `001-verifactu-base-aeat` (Fase 1 - Lista Priorizada)

## Phase 1: Setup & Foundational

**Purpose**: Preparativos iniciales y tareas bloqueantes de limpieza de tests.

- [x] T001 [P] Eliminar `app/domain/services/closing_service.py` por completo
- [x] T002 [P] Eliminar tests obsoletos en `tests/backend/unit/test_closing_service.py`
- [x] T003 Modificar `tests/backend/integration/test_cierre_fiscal_integration.py` para asegurar que usa exclusivamente `LedgerService`

---

## Phase 2: User Story 3 - Resolución de Deuda Técnica y Seguridad (Priority: P1)

**Goal**: Eliminar deuda técnica crítica y vulnerabilidades antes del paso a producción (API keys en disco, doble autenticación, excepciones silenciosas y tests no deterministas).

**Independent Test**: Ejecutar suite local y verificar con los endpoints (ej. `/bank/mock-auth` devuelve HTML escapado; endpoints arrojan errores de seguridad esperados).

### Tests (TDD) para US3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T004 [P] [US3] Crear/actualizar test para verificar XSS en `tests/backend/integration/test_bank_router.py` (o equivalente)
- [x] T005 [P] [US3] Crear test de autenticación para `/auth/setup` en `tests/backend/integration/test_auth_router.py`
- [x] T006 [P] [US3] Crear test para enrutador regex en `tests/backend/unit/test_agent_router.py`
- [x] T007 [P] [US3] Crear test para proveedores mock en producción en `tests/backend/unit/test_provider_factory.py`

### Implementation para US3

- [x] T008 [US2] Escapar datos en mock bancario (HTML encoding)
- [x] T009 [US3] Añadir dependencia `Depends(get_current_admin)` (o similar) en `/setup` dentro de `app/api/auth_router.py` (o proteger el primer inicio)
- [x] T010 [US4] Exigir firma y verificar `STRIPE_WEBHOOK_SECRET` en `app/api/stripe_router.py` (ahora en `subscriptions_router.py`)
- [x] T011 [US5] Corregir kwargs de factura rectificativa (usar `reason` y `amount` en lugar de `rectification_reason` y `base_imponible_rectificada`) en `app/api/billing_router.py`
- [x] T012 [US6] Importar `app_logger` y borrar referencias de configuración a Ollama en `app/infrastructure/adapters/llm_client.py`
- [x] T013 [US7] Lanzar `NotImplementedError` en `BankProviderFactory` (`app/infrastructure/adapters/bank_providers.py`) si `ENV` es production y se usa mock
- [x] T014 [US8] Usar regex `\b` en las palabras clave del enrutador de agentes en `app/domain/planner_orchestrator.py`
- [x] T015 [US9] Añadir validación de inputs de chat para evitar inyecciones básicas (ej: `<script>`) en `app/api/chat_router.py` (ahora en `routes.py`)
- [x] T016 [US10] Implementar stub `send_event` vacía en `app/adapters/alfonso_bridge.py` y resolver las llamadas faltantes que detienen la API.

---

## Phase 3: Polish & Cross-Cutting Concerns

**Purpose**: Validación final.

- [x] T017 Ejecutar los escenarios de `quickstart.md`
- [x] T018 Ejecutar la suite completa de tests de integración para comprobar que no hay regresiones

---

## Dependencies & Execution Order

- **Phase 1** debe realizarse primero (limpiar estado y adaptar el entorno base).
- **Phase 2 (US3)** puede realizarse con alta paralelización ya que muchos parches son independientes.
- T015 puede depender de cómo se estructure el resto del dominio, pero al ser un mock puede atacarse rápido.

---

## Phase 4: Convergence

**Purpose**: Resolver brechas detectadas entre la implementación actual y las prioridades de conformidad (P0).

- [x] T019 Implementar verificaciones reales en `get_compliance_declaration_dossier` per US1/FR-001 (CRITICAL - missing)
- [x] T020 Corregir `README.md` (y cualquier documentación) para reflejar XMLDSig enveloped en lugar de XAdES-BES per US1/FR-002 (HIGH - contradicts)
- [x] T021 Reemplazar el guardado de base64 del XML completo por una firma digital válida (XMLDSig) en el proceso de facturación per FR-002 (CRITICAL - partial)
---

## Phase 5: Tech Debt Cleanup (P1 - P5)

**Purpose**: Ejecutar el plan de limpieza para eliminar deuda técnica de arquitectura, tests y despliegue.

### Tests (TDD) para Deuda Técnica

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T022 [P] Borrar `tests/backend/unit/test_unit_stress.py` y tests irrelevantes sin asserts
- [x] T023 [P] Añadir test `test_approval_integration.py` (integration) simulando `alfonso_bridge` mockeado
- [x] T024 [P] Añadir test `test_ledger_properties.py` (unit) para asegurar la propiedad Debe == Haber en asientos

### Implementation - P1: Bugs

- [x] T025 [P] Eliminar asignación de roles basada en `pytest` de `ToolExecutionEngine`
- [x] T026 [P] Modificar `send_payment_reminder_email` para usar tabla `contacts` en lugar de `clients` y lanzar error sin email
- [x] T027 [P] Centralizar rutas estáticas y directorios `parents[2]` de `app/data/mail_db.py` y `app/data/calendar_db.py`
- [x] T028 Consolidar las migraciones (001, 015, 017 y 018) en `migrations/` y unificar el tipo de `invoice_id`

### Implementation - P2: Simulaciones

- [x] T029 [P] Eliminar `app/adapters/contaplus_parser.py` (y parsers A3 si existen)
- [x] T030 [P] Retirar la lógica simulada ("Rodamiento") en `process_inventory_document` de `inventory_service.py`
- [x] T031 [P] Retirar endpoints de firma con DNIe (hasta su implementación)
- [x] T032 [P] Eliminar `app/api/agents_router.py` (Guardián, boe_reader simulado)
- [x] T033 [P] Mover `scripts/dev_seeder.py` a `scripts/dev/` y purgar datos personales del repositorio

### Implementation - P3: Arquitectura y P5: Higiene

- [x] T034 [P] Aislar dominio: remover imports de `infrastructure` desde `app/domain/` e inyectar dependencias
- [x] T035 [P] Eliminar hack de `sys.meta_path` en `app/adapters/__init__.py` y renombrar imports afectados
- [x] T036 [P] Reducir `except Exception: pass` mudos a nivel global y lanzar excepción en utilidades criptográficas al fallar `decrypt()`
- [x] T037 [P] Limpiar `print("DEBUG: ...")`, código muerto y cabeceras obsoletas en el código
- [x] T038 [P] Fijar dependencias explícitamente en `requirements.txt`

---

## Phase 6: Refactorización de Tests (P1-P5 Follow-up)

**Purpose**: Arreglar los 30 tests fallidos y el error de recolección de tests resultantes de la profunda limpieza de deuda técnica, priorizando que la suite vuelva al 100% verde (estable) sin falsos negativos.

- [x] T039 [P] Eliminar o marcar como omitidos (`@pytest.mark.skip`) los tests de funcionalidades eliminadas (A3) en `tests/backend/integration/test_accounting_import.py`
- [x] T040 [P] Actualizar `tests/backend/integration/test_presupuestos_integration.py` y `tests/backend/unit/test_presupuestos_unit.py` para usar fixtures/tablas SQL en torno a `contacts` (antes `clients`)
- [x] T041 [P] Actualizar `tests/backend/integration/test_quotes_module.py` y `test_send_quote_email.py` alineando la lógica a `contacts`
- [x] T042 [P] Ajustar aserciones en `tests/backend/integration/test_signature_service.py` para esperar un fallo explícito (`ValueError`) en utilidades de cifrado
- [x] T043 [P] Reemplazar referencias a `app.adapters` por `app.infrastructure` en tests de integración como `tests/backend/integration/test_approval_integration.py` (y otros que lo importaban)
- [x] T044 [P] Corregir import erróneo `from core.api_client` por `from client.core.api_client` en `client/gui/dialogs/invoice.py`
- [x] T045 [P] Revisar roles e inyección `Depends` en `tests/backend/unit/test_auth_service.py` para que los tests pasen tras la remoción del bypass `pytest`
