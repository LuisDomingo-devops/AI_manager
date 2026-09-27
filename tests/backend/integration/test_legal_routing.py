import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.planner_orchestrator import PlannerOrchestrator
from app.adapters.memory import memory, vector_memory


@pytest.fixture(autouse=True)
def clean_databases():
    # Limpiar memoria de sesión y vectorial
    vector_memory.clear()
    from app.adapters.memory.memory import tenant_context
    tenant_context.set("default")
    # Limpiar SQLite
    sessions = memory.list_sessions()
    for s in sessions:
        memory.clear(s)
    yield
    vector_memory.clear()
    for s in memory.list_sessions():
        memory.clear(s)


@pytest.mark.anyio
@patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock)
async def test_accounting_queries_handled_by_orchestrator(mock_marcos_generate):
    """
    US1: Accounting queries should not be routed to Marcos. 
    They should remain operational in the orchestrator.
    """
    orchestrator = PlannerOrchestrator()
    session_id = "test_us1_session"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational"}', # intent
        '{"type": "message", "message": "El IVA total es 300 euros."}', # main response
        'Resumen de la conversación.' # summary
    ]

    result = await orchestrator.run(
        user_message="¿cuánto IVA he pagado?",
        llm=mock_llm,
        session_id=session_id,
        client_id="test_client"
    )

    # El agente Marcos no debería haber sido llamado
    mock_marcos_generate.assert_not_called()
    assert result["type"] == "chat"
    assert "El IVA total es 300 euros." in result["response"]


@pytest.mark.anyio
@patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock)
async def test_explicit_legal_query_delegated_to_marcos(mock_marcos_generate):
    """
    US2: Explicit legal queries should be routed to MarcosAgent.
    """
    orchestrator = PlannerOrchestrator()
    session_id = "test_us2_session"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational"}',
        'Resumen de la conversación.'
    ]
    
    # Marcos agent mock response
    mock_marcos_generate.return_value = "El artículo 154 de la normativa fiscal establece que..."

    result = await orchestrator.run(
        user_message="Explícame la normativa sobre deducción por vivienda",
        llm=mock_llm,
        session_id=session_id,
        client_id="test_client"
    )

    # El agente Marcos SÍ debería haber sido llamado
    mock_marcos_generate.assert_called_once()
    assert result["type"] == "chat"
    assert "normativa fiscal" in result["response"]


@pytest.mark.anyio
async def test_domain_stickiness_during_corrections():
    """
    US1: Test domain stickiness. Once in accounting context, 
    if a correction like 'mal' or 'error' comes, it should stick to the same domain.
    """
    orchestrator = PlannerOrchestrator()
    session_id = "test_stickiness_session"

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational"}', # intent 1
        '{"type": "message", "message": "Aquí tienes tu factura."}', # res 1
        'Resumen.',
        '{"type": "message", "message": "operational"}', # intent 2
        '{"type": "message", "message": "Corregido, aquí tienes los nuevos datos."}', # res 2
        'Resumen 2.'
    ]

    # Query 1: Operational
    await orchestrator.run(
        user_message="quiero ver mi libro mayor",
        llm=mock_llm,
        session_id=session_id,
        client_id="test_client"
    )
    
    meta1 = memory.get_metadata(session_id, "test_client")
    assert meta1["active_domain"] in (None, "general", "accounting")

    # Query 2: Correction
    with patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock) as mock_marcos:
        await orchestrator.run(
            user_message="está mal, falta la factura de ayer",
            llm=mock_llm,
            session_id=session_id,
            client_id="test_client"
        )
        mock_marcos.assert_not_called()
        
    meta2 = memory.get_metadata(session_id, "test_client")
    assert meta2["last_intent"] == "operational"


@pytest.mark.anyio
async def test_marcos_agent_cannot_emit_tool_calls():
    """
    US3: Verify MarcosAgent system prompt prevents JSON generation for tools.
    Here we test the LLM integration by verifying the actual prompt used for Marcos.
    """
    from app.domain.agents.marcos.marcos_agent import marcos_agent
    assert "No tienes acceso a herramientas ni puedes emitir tool_calls" in marcos_agent.system_prompt
    assert "Debes responder siempre en texto plano" in marcos_agent.system_prompt


@pytest.mark.anyio
@patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock)
async def test_unified_legal_disclaimer(mock_marcos_generate):
    """
    US4: The AVISO LEGAL disclaimer is appended only once in the planner orchestrator,
    and MarcosAgent does not emit it.
    """
    orchestrator = PlannerOrchestrator()
    session_id = "test_us4_session"
    
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    # It just generates intent, doesn't need to generate main response as Marcos is mocked
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational"}',
        'Resumen de la conversación.'
    ]

    mock_marcos_generate.return_value = "Esta es la información solicitada."

    result = await orchestrator.run(
        user_message="Dime qué pasa según el artículo 5 de la constitución española",
        llm=mock_llm,
        session_id=session_id,
        client_id="test_client"
    )

    mock_marcos_generate.assert_called_once()
    assert result["type"] == "chat"
    assert "Esta es la información solicitada." in result["response"]
    assert "AVISO LEGAL:" in result["response"]
    # Check it only appears once
    assert result["response"].count("AVISO LEGAL:") == 1
