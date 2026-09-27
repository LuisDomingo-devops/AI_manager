import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.planner_orchestrator import PlannerOrchestrator


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate = AsyncMock()
    return llm

@pytest.fixture
def session_memory_fixture():
    class DummyMemory:
        def __init__(self):
            self.history = []
            self.metadata = {}
            self.is_testing = True
        def add_message(self, session_id, role, content, client_id=None):
            self.history.append({"role": role, "content": content})
        def get_history(self, session_id, client_id=None):
            return self.history
        def clear(self, session_id):
            self.history = []
            self.metadata = {}
        def get_metadata(self, session_id, client_id=None):
            return self.metadata.get(session_id)
        def update_domain_context(self, session_id, **kwargs):
            if session_id not in self.metadata:
                self.metadata[session_id] = {}
            self.metadata[session_id].update(kwargs)
        def upsert_metadata(self, session_id, **kwargs):
            if session_id not in self.metadata:
                self.metadata[session_id] = {}
            self.metadata[session_id].update(kwargs)
        def update_summary(self, session_id, summary):
            pass
    return DummyMemory()

@pytest.mark.asyncio
async def test_intent_gate_conversational_early_return(mock_llm, session_memory_fixture):
    # Mock para que _classify_intent de devuelva conversational,
    # y el subsiguiente chat mode devuelva el saludo
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "conversational"}',
        "Hola, soy Alfonso, ¿en qué te ayudo?"
    ]

    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector), \
         patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.ConversationContextService") as mock_context_service_class:
        
        mock_context_service = mock_context_service_class.return_value
        mock_context_service.build_context = AsyncMock(return_value=("mock memory", [], []))
        mock_context_service.classify_and_log_corrections = AsyncMock()

        orchestrator = PlannerOrchestrator()
        result = await orchestrator.run(
            user_message="hola",
            llm=mock_llm,
            session_id="test_session"
        )
        
        # Validar el early return (es chat y cero tools)
        assert result["type"] == "chat"
        assert result["response"] == "Hola, soy Alfonso, ¿en qué te ayudo?"
        # El LLM solo se llam dos veces: para _classify_intent y para la generacin del chat
        assert mock_llm.generate.call_count == 2


@pytest.mark.asyncio
async def test_intent_gate_rejection_early_return(mock_llm, session_memory_fixture):
    # Mock para que _classify_intent de devuelva rejection,
    # y el subsiguiente chat mode devuelva la confirmacin de cancelacin
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "rejection"}',
        "De acuerdo, cancelado."
    ]

    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector), \
         patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.ConversationContextService") as mock_context_service_class:
        
        mock_context_service = mock_context_service_class.return_value
        mock_context_service.build_context = AsyncMock(return_value=("mock memory", [], []))
        mock_context_service.classify_and_log_corrections = AsyncMock()

        orchestrator = PlannerOrchestrator()
        result = await orchestrator.run(
            user_message="no",
            llm=mock_llm,
            session_id="test_session"
        )
        
        # Validar el early return (es chat y cero tools)
        assert result["type"] == "chat"
        assert result["response"] == "De acuerdo, cancelado."
        assert mock_llm.generate.call_count == 2


@pytest.mark.asyncio
async def test_intent_gate_operational_preserves_react(mock_llm, session_memory_fixture):
    # Mock para que _classify_intent devuelva operational.
    # El orchestrator seguir al bucle ReAct.
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational"}',
        '{"type": "tool_call", "tool_name": "calendar_open_ui", "tool_args": {}}'
    ]

    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []
    
    mock_bridge = AsyncMock()
    mock_bridge.send_command.return_value = {"status": "success", "result": "operacin exitosa"}

    with patch("app.domain.planner_orchestrator.memory", session_memory_fixture), \
         patch("app.domain.planner_orchestrator.vector_memory", mock_vector), \
         patch("app.infrastructure.adapters.alfonso_bridge.bridge", mock_bridge), \
         patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.ConversationContextService") as mock_context_service_class:
        
        mock_context_service = mock_context_service_class.return_value
        mock_context_service.build_context = AsyncMock(return_value=("mock memory", [], []))
        mock_context_service.classify_and_log_corrections = AsyncMock()

        orchestrator = PlannerOrchestrator()
        
        # Necesitamos mockear stream_chat para la parte operativa (ReAct)
        async def mock_stream_chat(messages):
            yield '{"type": "tool_call", "tool_name": "calendar_open_ui", "tool_args": {}}'
        mock_llm.stream_chat = mock_stream_chat

        result = await orchestrator.run(
            user_message="procesa las facturas",
            llm=mock_llm,
            session_id="test_session"
        )
        
        # Validar que lleg al router/ReAct y devolvi el tool correspondiente
        assert result["type"] == "tool"
        assert result["tool"] == "calendar_open_ui"
        # 1 para classify (generate) y ReAct usa stream_chat
        assert mock_llm.generate.call_count == 2
