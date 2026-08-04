import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.planner_orchestrator import PlannerOrchestrator


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate = AsyncMock()
    return llm


@pytest.mark.asyncio
async def test_orchestrator_chat_flow(mock_llm, session_memory_fixture):
    session_memory_fixture.clear("test_session")
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector):
        mock_llm.generate.return_value = "Hola Luis, soy tu asistente."
        
        orchestrator = PlannerOrchestrator()
        result = await orchestrator.run(
            user_message="Hola Alfonso",
            llm=mock_llm,
            session_id="test_session"
        )
        
        assert result["type"] == "chat"
        assert result["response"] == "Hola Luis, soy tu asistente."
        
        # Debe haber guardado tanto el mensaje del usuario como el del asistente en memoria
        history = session_memory_fixture.get_history("test_session")
        assert len(history) == 2
        assert history[0]["content"] == "Hola Alfonso"
        assert history[1]["content"] == "Hola Luis, soy tu asistente."


@pytest.mark.asyncio
async def test_orchestrator_client_tool_flow(mock_llm, session_memory_fixture):
    session_memory_fixture.clear("test_session")
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector):
        # El LLM responde con una herramienta cliente: click
        mock_llm.generate.return_value = '{"tool": "click", "args": {"x": 100, "y": 200}}'
        
        # Mock de alfonso_bridge
        mock_bridge = AsyncMock()
        mock_bridge.send_command.return_value = {"status": "success", "result": "click exitoso"}
        
        with patch("app.adapters.alfonso_bridge.bridge", mock_bridge):
            orchestrator = PlannerOrchestrator()
            result = await orchestrator.run(
                user_message="haz click en la pantalla",
                llm=mock_llm,
                session_id="test_session"
            )
            
            assert result["type"] == "tool"
            assert result["execution"] == "client"
            assert result["tool"] == "click"
            assert result["result"] == {}


@pytest.mark.asyncio
async def test_orchestrator_server_tool_flow(mock_llm, session_memory_fixture):
    session_memory_fixture.clear("test_session")
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector):
        # El LLM responde con la respuesta conversacional en el segundo turno (el primer turno se enruta directo por heurística)
        mock_llm.generate.return_value = 'La fecha actual es jueves.'
        
        mock_tool_func = AsyncMock(return_value={"status": "ok", "human": "jueves"})
        
        with patch("app.domain.planner_orchestrator.get_tool", return_value=mock_tool_func):
            orchestrator = PlannerOrchestrator()
            result = await orchestrator.run(
                user_message="qué hora es",
                llm=mock_llm,
                session_id="test_session"
            )
            
            assert result["type"] == "chat"
            assert result["response"] == "La fecha actual es jueves."
            mock_tool_func.assert_called_once_with()


@pytest.mark.asyncio
async def test_orchestrator_mail_bypass_flow(mock_llm, session_memory_fixture):
    session_memory_fixture.clear("test_session")
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    # Mock del LLM para que devuelva la respuesta final conversacional en el segundo turno (el primer turno se enruta directo)
    mock_llm.generate.return_value = "Correos de prueba generados correctamente."

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector):
        
        mock_mail_func = AsyncMock(return_value={"status": "ok", "message": "Inyectados"})
        
        with patch("app.domain.planner_orchestrator.get_tool", return_value=mock_mail_func):
            orchestrator = PlannerOrchestrator()
            result = await orchestrator.run(
                user_message="Genera correos de prueba",
                llm=mock_llm,
                session_id="test_session"
            )
            
            assert result["type"] == "chat"
            assert result["response"] == "Correos de prueba generados correctamente."
            mock_mail_func.assert_called_once()
            mock_llm.generate.assert_called_once()


@pytest.mark.asyncio
async def test_orchestrator_composite_bypass_flow(mock_llm, session_memory_fixture):
    session_memory_fixture.clear("test_session")
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    # Mock del LLM para que devuelva la llamada a la primera herramienta del flujo compuesto
    mock_llm.generate.return_value = '{"tool": "calendar_open_ui", "args": {}}'

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector):
        
        mock_composite_func = AsyncMock(return_value={"status": "ok", "message": "Calendario abierto"})
        
        with patch("app.domain.planner_orchestrator.get_tool", return_value=mock_composite_func):
            orchestrator = PlannerOrchestrator()
            result = await orchestrator.run(
                user_message="Abre el calendario",
                llm=mock_llm,
                session_id="test_session"
            )
            
            assert result["type"] == "tool"
            assert result["tool"] == "calendar_open_ui"
            assert result["result"] == {}
            mock_llm.generate.assert_not_called()
