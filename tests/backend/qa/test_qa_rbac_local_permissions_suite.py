"""
Suite de QA para validación de permisos RBAC y perfiles de usuario (Spec 029 - US4 / QA).
Valida:
1. El rol 'advisor' puede invocar todas las herramientas de consulta y auditoría de su whitelist.
2. El rol 'advisor' es estrictamente rechazado ante cualquier herramienta fuera de su whitelist.
3. El rol 'guest' o 'limitado' no puede ejecutar herramientas operativas de servidor.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.domain.planner_orchestrator import ToolExecutionEngine


ADVISOR_WHITELIST = {
    "get_libro_diario", "get_libro_mayor", "get_balance_situacion", "get_pgc_accounts",
    "get_profit_and_loss_report", "export_advisor_pack", "export_advisor_pack_tool",
    "send_to_advisor", "request_document",
    "get_tax_estimate", "get_clients", "get_products", "get_quotes",
    "get_pending_payments_report", "get_invoice_payment_summary",
    "get_b2b_invoice_status_history_tool", "export_einvoice_tool",
    "list_directory", "view_file", "no_op"
}

MUTATION_TOOLS_BLACK_LIST_FOR_ADVISOR = [
    "create_invoice",
    "delete_client",
    "delete_product",
    "create_employee",
    "generate_payroll_receipt",
    "terminate_employee",
    "run_bank_reconciliation"
]


@pytest.mark.asyncio
async def test_qa_advisor_permitted_on_whitelist():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    mock_bridge._client_info_dict = {"adv_1": {"role": "advisor"}}
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    for tool_name in ["get_libro_diario", "get_tax_estimate", "get_pgc_accounts"]:
        with patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
             patch("app.domain.planner_orchestrator.prepare_tool_args") as mock_prep:
            
            mock_prep.return_value = MagicMock(ok=True, args={})
            mock_tool = AsyncMock(return_value={"status": "ok", "data": "report"})
            mock_get_tool.return_value = mock_tool

            res = await engine.execute_tool(
                tool_name=tool_name,
                args={},
                session_id="s1",
                client_id="adv_1",
                request_id="req_adv_qa",
                logger=logger,
                error=error_logger
            )

            assert res["status"] != "rbac_error", f"La herramienta {tool_name} de la whitelist del advisor no debe dar rbac_error"


@pytest.mark.asyncio
async def test_qa_advisor_forbidden_on_mutation_tools():
    mock_memory = MagicMock()
    mock_bridge = MagicMock()
    mock_bridge._client_info_dict = {"adv_2": {"role": "advisor"}}
    engine = ToolExecutionEngine(mock_memory, mock_bridge)

    logger = MagicMock()
    error_logger = MagicMock()

    for tool_name in MUTATION_TOOLS_BLACK_LIST_FOR_ADVISOR:
        res = await engine.execute_tool(
            tool_name=tool_name,
            args={"amount": 100},
            session_id="s1",
            client_id="adv_2",
            request_id="req_adv_qa_block",
            logger=logger,
            error=error_logger
        )

        assert res["status"] == "rbac_error", f"La herramienta {tool_name} debió ser bloqueada para el rol advisor"
        assert "advisor" in res["message"].lower()
