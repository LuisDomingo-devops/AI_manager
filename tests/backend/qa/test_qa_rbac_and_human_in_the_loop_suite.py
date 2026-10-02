"""
Suite de QA para Human-in-the-Loop y RBAC (Spec 029 - US3 / QA).
Valida:
1. Toda herramienta incluida en CRITICAL_TOOLS detiene su ejecución desatendida y requiere aprobación explícita.
2. Ninguna herramienta crítica se ejecuta si la aprobación es rechazada o timeout.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.domain.actions import CRITICAL_TOOLS
from app.domain.planner_orchestrator import ToolExecutionEngine


@pytest.mark.asyncio
async def test_qa_all_critical_tools_enforce_human_approval():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    # Probar que para cada tool de CRITICAL_TOOLS se solicita aprobación antes de ejecutar
    for tool_name in CRITICAL_TOOLS:
        with patch("app.domain.services.approval_service.approval_service.request_approval", new_callable=AsyncMock) as mock_req, \
             patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
             patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "OK")):
            
            mock_req.return_value = False
            mock_tool = AsyncMock()
            mock_get_tool.return_value = mock_tool

            res = await engine.execute_tool(
                tool_name=tool_name,
                args={"test": "qa_param"},
                session_id="qa_session",
                client_id="qa_client",
                request_id="qa_req_001",
                logger=logger,
                error=error_logger
            )

            # Debe haber sido cancelada
            assert res["status"] == "cancelled", f"La herramienta crítica {tool_name} no fue cancelada ante rechazo de aprobación"
            # Y la herramienta subyacente NUNCA debió ser invocada
            mock_tool.assert_not_called()
            # La solicitud de aprobación debió realizarse
            mock_req.assert_awaited_once()
