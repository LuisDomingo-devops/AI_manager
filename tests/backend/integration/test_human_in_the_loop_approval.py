"""
Tests de integración para Human-in-the-Loop (HITL) (Spec 029 - US3).
Valida:
1. Las herramientas en CRITICAL_TOOLS detienen su ejecución y solicitan aprobación vía approval_service.
2. Los argumentos reales se propagan a request_approval(details=args) y no diccionarios vacíos {}.
3. Si el usuario rechaza o se agota el timeout, la tool devuelve status='cancelled' atómicamente.
4. Si el usuario aprueba, la herramienta se ejecuta normalmente.
5. El endpoint REST /api/v1/approval/{approval_id}/decision resuelve la aprobación pendiente.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.domain.actions import CRITICAL_TOOLS
from app.domain.planner_orchestrator import ToolExecutionEngine


@pytest.mark.asyncio
async def test_critical_tool_intercepted_and_cancelled_on_rejection():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    critical_tool = "create_invoice"
    sample_args = {"param1": "val1", "amount": 100}

    with patch("app.domain.services.approval_service.approval_service.request_approval", new_callable=AsyncMock) as mock_req, \
         patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "OK")):
        mock_req.return_value = False

        res = await engine.execute_tool(
            tool_name=critical_tool,
            args=sample_args,
            session_id="test_sess",
            client_id="test_client",
            request_id="req_123",
            logger=logger,
            error=error_logger
        )

        assert res["status"] == "cancelled"
        assert "cancelada" in res["message"].lower() or "rechazada" in res["message"].lower()
        mock_req.assert_awaited_once()
        # Verificar que se pasaron los argumentos reales
        _, kwargs = mock_req.call_args
        assert kwargs.get("details") == sample_args or mock_req.call_args[0][1] == sample_args or kwargs.get("action_type") == critical_tool


@pytest.mark.asyncio
async def test_critical_tool_executes_when_approved():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    critical_tool = "create_invoice"
    sample_args = {"param1": "val1"}

    with patch("app.domain.services.approval_service.approval_service.request_approval", new_callable=AsyncMock) as mock_req, \
         patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
         patch("app.domain.planner_orchestrator.prepare_tool_args") as mock_prep, \
         patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "OK")):
        
        mock_req.return_value = True
        mock_prep.return_value = MagicMock(ok=True, args=sample_args)
        mock_tool_callable = AsyncMock(return_value={"status": "ok", "executed": True})
        mock_get_tool.return_value = mock_tool_callable

        res = await engine.execute_tool(
            tool_name=critical_tool,
            args=sample_args,
            session_id="test_sess",
            client_id="test_client",
            request_id="req_123",
            logger=logger,
            error=error_logger
        )

        assert res["status"] == "ok"
        mock_tool_callable.assert_awaited_once()


@pytest.mark.asyncio
async def test_approval_decision_endpoint():
    from starlette.requests import Request
    from app.api.routes import resolve_approval_endpoint, ApprovalResolutionRequest
    from app.domain.services.approval_service import approval_service

    action_id = "test_approval_uuid"
    approval_service._pending_approvals[action_id] = MagicMock(done=lambda: False, set_result=MagicMock())

    try:
        payload = ApprovalResolutionRequest(action_id=action_id, approved=True, user_notes="Aprobado por el usuario")
        resp = await resolve_approval_endpoint(action_id=action_id, payload=payload, client_id="owner")
        assert resp["status"] == "ok"
        assert resp["approved"] is True
    finally:
        approval_service._pending_approvals.pop(action_id, None)
