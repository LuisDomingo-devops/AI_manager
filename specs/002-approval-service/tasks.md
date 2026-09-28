# Tasks: Saneamiento y Desacoplamiento de ApprovalService (Spec 002)

**Objetivo**: Erradicar el mock global `autouse=True` de `ApprovalService` en `conftest.py`, corregir las llamadas estáticas inválidas en `payroll_tools.py` y `aeat_automation_tools.py`, y blindar los caminos de rechazo humano mediante TDD estricto.

---

## Phase 1: Setup y Preparación

- [x] T001 Crear el directorio de logs de ejecución TDD en `tests/logs/spec002/`
- [x] T002 Apuntar `.specify/feature.json` a `specs/002-approval-service`

---

## Phase 2: User Story 1 (P1) — Contratos e Invocación de ApprovalService

**Meta**: Garantizar que `ApprovalService` sea seguro tanto si se invoca como instancia como si se invoca desde la clase, y validar sus contratos asíncronos.

### Tests TDD (Red)
- [x] T003 [P] [US1] Crear test unitario en `tests/backend/unit/test_approval_service_contracts.py` verificando el comportamiento de resolución (`True`, `False`, `timeout`) y la llamada polimórfica clase/instancia.
- [x] T004 [US1] Ejecutar `test_approval_service_contracts.py` y verificar estado Red.

### Implementación TDD (Green)
- [x] T005 [US1] Añadir compatibilidad de clase en `ApprovalService` en `app/domain/services/approval_service.py` delegando a la instancia singleton `approval_service`.
- [x] T006 [US1] Sustituir las 3 llamadas directas a la clase en `app/tools/server/payroll_tools.py` por la instancia `approval_service`.
- [x] T007 [US1] Sustituir las 12 llamadas directas a la clase en `app/tools/server/aeat_automation_tools.py` por la instancia `approval_service`.

### Verificación (TDD)
- [x] T008 [US1] Re-ejecutar `test_approval_service_contracts.py` y guardar log en `tests/logs/spec002/us1_green.log`.

---

## Phase 3: User Story 2 (P1) — Desacoplamiento del Mock Global en Tests

**Meta**: Eliminar `autouse=True` en `tests/conftest.py` y habilitar fixtures declarativos sin ocultar fallos reales.

### Tests TDD (Red)
- [x] T009 [P] [US2] Crear test de integración en `tests/backend/integration/test_approval_rejection_workflows.py` simulando rechazo explícito (`approved=False`) y comprobando que las herramientas laborales y de la AEAT abortan sin mutar datos.
- [x] T010 [US2] Retirar el decorador `autouse=True` del fixture `mock_approval_service` en `tests/conftest.py` y medir los fallos que afloran.

### Implementación TDD (Green)
- [x] T011 [US2] Configurar en `tests/conftest.py` los fixtures nombrados `mock_approval_granted` y `mock_approval_rejected`.
- [x] T012 [US2] Actualizar los tests de integración que requieren aprobación explícita para que declaren `mock_approval_granted`.

### Verificación (TDD)
- [x] T013 [US2] Re-ejecutar `test_approval_rejection_workflows.py` y tests afectados, guardando log en `tests/logs/spec002/us2_green.log`.

---

## Phase 4: User Story 3 (P2) — Suite de QA y Gobernanza Human-in-the-Loop

**Meta**: Certificar con un test de QA de alto nivel que las operaciones irreversibles nunca se ejecutan sin autorización.

### Tests TDD
- [x] T014 [P] [US3] Crear test de QA en `tests/backend/qa/test_approval_governance_suite.py` evaluando la matriz de autorización (aprobación concedida, rechazada, expirada) en liquidaciones y borrados.
- [x] T015 [US3] Ejecutar `test_approval_governance_suite.py` y verificar que pasa al 100%, guardando log en `tests/logs/spec002/us3_green.log`.

---

## Phase 5: Validación de Toda la Suite del Repositorio

- [x] T016 Ejecutar la suite completa de pruebas (`pytest tests -v`) y guardar la salida completa en `pytest-logs.txt`.
- [x] T017 Verificar la ausencia de regresiones colaterales y consolidar commit de entrega formal de la Spec 002.
