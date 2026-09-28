# Feature Specification: Saneamiento y Desacoplamiento de ApprovalService (Spec 002)

**Feature Branch**: `002-approval-service`  
**Created**: 2026-09-28  
**Status**: Ready for Planning  
**Input**: Erradicación del mock global de `ApprovalService` en `conftest.py`, corrección de invocaciones inválidas de clase (`ApprovalService.request_approval(...)`), e inyección determinista de dependencias para validación humana Out-of-Band.

---

## 1. Contexto y Problema

El sistema Alfonso AI Konta incorpora un mecanismo de seguridad y gobernanza humana (Human-in-the-Loop / Out-of-Band) denominado `ApprovalService`. Este servicio suspende la ejecución de acciones críticas e irreversibles (anulación de facturas ya declaradas a la AEAT, emisión de nóminas y despidos, liquidación de modelos tributarios y borrado de clientes/productos) mediante un WebSocket contra el cliente local hasta recibir confirmación explícita del usuario.

### Defectos Críticos Detectados en la Auditoría:
1. **Mock Global Indiscriminado (`conftest.py`)**:
   En `tests/conftest.py` existe un fixture automático:
   ```python
   @pytest.fixture(autouse=True)
   def mock_approval_service():
       with patch("app.domain.services.approval_service.ApprovalService.request_approval", new_callable=AsyncMock) as mocked:
           mocked.return_value = True
           yield mocked
   ```
   Este fixture intercepta indiscriminadamente todas las pruebas del repositorio, forzando que cualquier solicitud de aprobación siempre devuelva `True`. Como consecuencia:
   - **Oculta bugs de ejecución en caliente**: Módulos como `payroll_tools.py` y `aeat_automation_tools.py` invocan `await ApprovalService.request_approval(...)` como método estático sobre la clase, en lugar de invocar la instancia `approval_service` o usar el método de instancia `self`. En tiempo de ejecución real sin el patch de unittest, esto lanzaría un error (`TypeError: missing 1 required positional argument: 'self'`).
   - **Falsea el cumplimiento legal y de seguridad**: Ningún test verifica qué sucede cuando el usuario humano **rechaza** la operación o si se produce un **timeout** del WebSocket, dejando los caminos de rechazo completamente ciegos.
2. **Inconsistencia de Arquitectura**:
   En `billing_tools.py`, `bank_tools.py` y `advisor_tools.py` se utiliza `from app.domain.services.approval_service import approval_service`, mientras que en `payroll_tools.py` y `aeat_automation_tools.py` se importa la clase cruda `ApprovalService`.

---

## 2. Comportamiento Esperado

1. **Eliminación del Mock Global `autouse=True`**:
   - `tests/conftest.py` NO debe contener ningún fixture `autouse` que parchee `ApprovalService` globalmente.
   - Los tests que requieran simular respuestas afirmativas o negativas de aprobación humana deben solicitar explícitamente un fixture controlado (ej. `approved_user`, `rejected_user`, `timeout_user`).
2. **Invocación Unificada y Resiliente**:
   - En todos los módulos de producción (`payroll_tools.py`, `aeat_automation_tools.py`, `billing_tools.py`, `bank_tools.py`), las llamadas a la aprobación humana deben utilizar la instancia canónica `approval_service.request_approval(...)` o soporte de método de clase seguro en `ApprovalService`.
3. **Manejo Determinista de Rechazos y Timeouts**:
   - Toda herramienta que reciba `approved = False` debe abortar limpiamente la operación, retornar el estado `pending_confirmation` / `rejected_by_user`, registrar el evento de auditoría correspondiente y no aplicar ninguna mutación a la base de datos contable o fiscal.

---

## 3. Requisitos Funcionales y Criterios de Aceptación

### User Story 1 (P1): Erradicación de Invocaciones Inválidas de Clase en Herramientas de Producción
Como motor de ejecución de herramientas,  
quiero que `payroll_tools.py` y `aeat_automation_tools.py` utilicen la instancia canónica o un método interoperable de `ApprovalService`,  
para que las operaciones laborales y fiscales no colapsen en tiempo de ejecución real al intentar invocar un método de instancia sin `self`.

**Criterios de Aceptación**:
1. `payroll_tools.py` (3 ocurrencias: `create_employee_tool`, `calculate_payroll_tool`, `create_settlement_tool`) debe invocar `approval_service.request_approval(...)`.
2. `aeat_automation_tools.py` (12 ocurrencias de modelos tributarios: 303, 111, 115, 130, 390, 190, 180, etc.) debe invocar `approval_service.request_approval(...)`.
3. `ApprovalService` en `app/domain/services/approval_service.py` debe ofrecer un método de clase o alias `@classmethod` para `request_approval` como salvaguarda defensiva ante llamadas directas a la clase.

---

### User Story 2 (P1): Eliminación del Mock Global y Creación de Fixtures Explícitos
Como desarrollador y auditor de calidad,  
quiero que ningún mock global conceda aprobaciones automáticas sin que el test lo declare explícitamente,  
para certificar con rigor tanto los caminos de éxito como los de rechazo humano.

**Criterios de Aceptación**:
1. En `tests/conftest.py`, el decorador `autouse=True` de `mock_approval_service` queda eliminado.
2. Se definen fixtures parametrizables/nombrados (`mock_approval_granted`, `mock_approval_rejected`, `mock_approval_timeout`) para los tests que deseen simular interacción con el frontend.
3. Los tests existentes que prueban herramientas sensibles declaran explícitamente el fixture de aprobación, evitando dependencias mágicas.

---

### User Story 3 (P2): Cobertura TDD Completa de Flujos de Rechazo y Timeout
Como responsable de cumplimiento normativo (Ley Antifraude / Out-of-Band),  
quiero una batería exhaustiva de tests unitarios, de integración y QA que valide el comportamiento del sistema cuando el usuario humano cancela o ignora una acción irreversible,  
para garantizar que ninguna transacción se ejecuta sin consentimiento humano verificable.

**Criterios de Aceptación**:
1. Test unitario en `tests/backend/unit/test_approval_service_contracts.py` validando la resolución positiva, negativa y por expiración de timeout en `ApprovalService`.
2. Test de integración en `tests/backend/integration/test_approval_rejection_workflows.py` verificando que cuando `approved=False` en nóminas o liquidación de modelos AEAT, no se generan ficheros AFI, no se modifican nóminas ni se alteran asientos contables.
3. Test de QA en `tests/backend/qa/test_approval_governance_suite.py` certificando la gobernanza completa del Human-in-the-Loop.

---

## 4. Archivos Afectados

1. `tests/conftest.py`
2. `app/domain/services/approval_service.py`
3. `app/tools/server/payroll_tools.py`
4. `app/tools/server/aeat_automation_tools.py`
5. `tests/backend/unit/test_approval_service_contracts.py` (Nuevo)
6. `tests/backend/integration/test_approval_rejection_workflows.py` (Nuevo)
7. `tests/backend/qa/test_approval_governance_suite.py` (Nuevo)
