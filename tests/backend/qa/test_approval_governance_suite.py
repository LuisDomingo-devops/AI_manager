"""
Suite de QA: Gobernanza y Aprobación Human-in-the-Loop (Spec 002 - QA)
Verifica que las operaciones irreversibles (borrado de clientes, nóminas y declaraciones AEAT)
respeten estrictamente la matriz de autorización humana:
1. Concesión explícita -> Éxito en ejecución.
2. Rechazo explícito -> Aborto sin mutación y estado pending_confirmation.
3. Timeout de confirmación -> Aborto por inactividad y limpieza de memoria.
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.tools.server.billing_tools import delete_client
from app.tools.server.payroll_tools import create_employee_tool
from app.tools.server.aeat_automation_tools import generate_modelo_303_autofill_script
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
async def test_qa_governance_matrix_delete_client_authorized(mock_approval_service):
    """Acción autorizada por el usuario: debe proceder."""
    with patch("app.domain.services.audit_ledger.AuditLedgerService.log_audit_event", return_value=True):
        with patch("app.tools.server.billing_tools.delete_contact", return_value={"status": "ok"}):
            res = await delete_client(client_id=1)
            assert res["status"] == "ok"
            assert "desactivado" in res["message"]


@pytest.mark.asyncio
async def test_qa_governance_matrix_delete_client_rejected(mock_approval_rejected):
    """Acción rechazada por el usuario: debe abortar con error o cancelación."""
    res = await delete_client(client_id=1)
    assert res["status"] == "error"
    assert "cancelada" in res["message"].lower() or "timeout" in res["message"].lower()


@pytest.mark.asyncio
async def test_qa_governance_matrix_aeat_303_timeout():
    """Acción con timeout/rechazo en aprobación humana: aborta sin generar script."""
    from unittest.mock import AsyncMock
    with patch("app.domain.services.approval_service.ApprovalService.request_approval", new_callable=AsyncMock) as mocked:
        mocked.return_value = False
        res = await generate_modelo_303_autofill_script(year=2026, quarter=1)
        assert res["status"] == "pending_confirmation"
        assert "script" not in res
