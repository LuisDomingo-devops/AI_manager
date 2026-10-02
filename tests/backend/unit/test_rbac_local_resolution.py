"""
Tests unitarios para la resolución de permisos RBAC locales y multi-tenant (Spec 029 - US4).
Valida:
1. Peticiones locales de escritorio con client_id=None o vacío asumen rol 'owner' (no 'guest').
2. Peticiones con client_id='default' o 'local' asumen rol 'owner'.
3. Peticiones con rol 'advisor' están restringidas estrictamente a su whitelist de solo lectura.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.domain.planner_orchestrator import ToolExecutionEngine


@pytest.mark.asyncio
async def test_local_desktop_client_none_resolves_to_owner():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    sample_tool = "get_clients"
    sample_args = {}

    with patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
         patch("app.domain.planner_orchestrator.prepare_tool_args") as mock_prep:
        
        mock_prep.return_value = MagicMock(ok=True, args=sample_args)
        mock_tool_callable = AsyncMock(return_value={"status": "ok", "clients": []})
        mock_get_tool.return_value = mock_tool_callable

        res = await engine.execute_tool(
            tool_name=sample_tool,
            args=sample_args,
            session_id="local_session",
            client_id=None,
            request_id="req_local_1",
            logger=logger,
            error=error_logger
        )

        assert res["status"] != "rbac_error", "client_id=None no debe ser tratado como guest con rbac_error"
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_local_desktop_default_tenant_resolves_to_owner():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    sample_tool = "get_products"
    sample_args = {}

    with patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
         patch("app.domain.planner_orchestrator.prepare_tool_args") as mock_prep:
        
        mock_prep.return_value = MagicMock(ok=True, args=sample_args)
        mock_tool_callable = AsyncMock(return_value={"status": "ok", "products": []})
        mock_get_tool.return_value = mock_tool_callable

        res = await engine.execute_tool(
            tool_name=sample_tool,
            args=sample_args,
            session_id="local_session",
            client_id="default",
            request_id="req_local_2",
            logger=logger,
            error=error_logger
        )

        assert res["status"] != "rbac_error", "client_id='default' debe ser 'owner' y no fallar con rbac_error"
        assert res["status"] == "ok"


@pytest.mark.asyncio
async def test_advisor_role_blocked_on_mutation_tools():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    mock_bridge._client_info_dict = {"advisor_client_1": {"role": "advisor"}}
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    mutation_tool = "create_invoice"
    sample_args = {"client_id": "c1", "amount": 500}

    res = await engine.execute_tool(
        tool_name=mutation_tool,
        args=sample_args,
        session_id="adv_session",
        client_id="advisor_client_1",
        request_id="req_adv_1",
        logger=logger,
        error=error_logger
    )

    assert res["status"] == "rbac_error"
    assert "advisor" in res["message"].lower() or "denegado" in res["message"].lower()
