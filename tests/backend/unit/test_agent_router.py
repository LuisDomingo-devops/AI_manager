import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch('app.domain.agents.security.security_agent.security_agent.generate_response', new_callable=AsyncMock)
@patch('app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response', new_callable=AsyncMock)
@patch('app.domain.agents.excel.excel_agent.excel_agent.generate_response', new_callable=AsyncMock)
async def test_agent_router_regex_boundaries(mock_excel, mock_marcos, mock_security):
    from app.domain.planner_orchestrator import SpecializedAgentRouter
    from unittest.mock import Mock
    orchestrator = SpecializedAgentRouter(memory=Mock())
    logger = Mock()
    
    mock_security.return_value = "CyberSecurityAgent"
    mock_marcos.return_value = "FiscalAgent"
    
    # "seguridad" should go to CyberSecurityAgent
    res1 = await orchestrator.route_if_applicable("Necesito ayuda con la seguridad", "s1", "c1", logger)
    assert res1 is not None
    assert res1["response"] == "CyberSecurityAgent"
    
    # "Seguridad Social" should NOT go to CyberSecurityAgent (handled by LLM normally)
    res2 = await orchestrator.route_if_applicable("Pago de la Seguridad Social", "s1", "c1", logger)
    assert (res2 is None) or (res2.get("response") != "CyberSecurityAgent")
    
    # "iva" should go to FiscalAgent (marcos)
    res3 = await orchestrator.route_if_applicable("Pagar el iva trimestral", "s1", "c1", logger)
    assert res3 is not None
    assert res3["response"] == "FiscalAgent"
    
    # "pasiva" or "nativa" should NOT trigger FiscalAgent
    res4 = await orchestrator.route_if_applicable("Actividad pasiva y nativa", "s1", "c1", logger)
    assert (res4 is None) or (res4.get("response") != "FiscalAgent")
