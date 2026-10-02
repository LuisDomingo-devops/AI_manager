"""
Tests de integración para el ciclo de vida del chat en streaming asíncrono (Spec 029 - US2).
Valida:
1. Streaming de texto palabra a palabra (emisión de {"type": "chunk", "text": ...}).
2. Streaming de llamada a herramientas tipado Pydantic (LLMDecisionEnvelope) sin errores de diccionario ni "tool" in data.
3. Cierre correcto del stream y compatibilidad con payloads legacy.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.domain.schemas import IntentType, LLMDecisionEnvelope
from app.domain.planner_orchestrator import PlannerOrchestrator


class FakeStreamLLM:
    def __init__(self, chunks):
        self.chunks = chunks

    async def stream_chat(self, messages):
        for chunk in self.chunks:
            yield chunk


@pytest.mark.asyncio
async def test_run_stream_conversational_text():
    """Valida que una respuesta conversacional se emita fragmento a fragmento."""
    chunks = ["Hola, ", "¿en qué ", "puedo ", "ayudarte?"]
    fake_llm = FakeStreamLLM(chunks)
    
    orchestrator = PlannerOrchestrator(llm=fake_llm)
    orchestrator.agent_router = MagicMock(route_if_applicable=AsyncMock(return_value=None))
    orchestrator.context_service = MagicMock(build_context=AsyncMock(return_value=("", [], {})))
    orchestrator.memory.get_history = MagicMock(return_value=[])
    orchestrator.memory.add_message = MagicMock()

    emitted_events = []
    async for raw_event in orchestrator.run_stream("Hola", llm=fake_llm):
        emitted_events.append(json.loads(raw_event))

    chunk_events = [e for e in emitted_events if e.get("type") == "chunk"]
    assert len(chunk_events) == len(chunks)
    assert "".join(c["text"] for c in chunk_events) == "Hola, ¿en qué puedo ayudarte?"


@pytest.mark.asyncio
async def test_run_stream_tool_call_envelope_typed_access():
    """Valida que un stream con tool_call ejecute la herramienta accediendo a atributos tipados sin fallar por 'tool' in data."""
    tool_json_chunks = [
        '{"type": "tool_call", ',
        '"tool_name": "list_directory", ',
        '"tool_args": {"path": "."}}'
    ]
    fake_llm = FakeStreamLLM(tool_json_chunks)

    mock_exec_engine = MagicMock()
    mock_exec_engine.execute_tool = AsyncMock(return_value={"status": "ok", "items": ["file1.txt"]})

    orchestrator = PlannerOrchestrator(llm=fake_llm)
    orchestrator.agent_router = MagicMock(route_if_applicable=AsyncMock(return_value=None))
    orchestrator.context_service = MagicMock(build_context=AsyncMock(return_value=("", [], {})))
    orchestrator.memory.get_history = MagicMock(return_value=[])
    orchestrator.memory.add_message = MagicMock()
    orchestrator.execution_engine = mock_exec_engine

    emitted_events = []
    async for raw_event in orchestrator.run_stream("lista los archivos", llm=fake_llm):
        emitted_events.append(json.loads(raw_event))

    tool_events = [e for e in emitted_events if e.get("type") == "tool"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "list_directory"
    assert tool_events[0]["result"]["status"] == "ok"
    mock_exec_engine.execute_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_stream_legacy_tool_call_backward_compatibility():
    """Valida que un stream con formato legacy {"tool": ...} también se ejecute sin excepciones."""
    legacy_chunks = ['{"tool": "list_directory", "args": {"path": "/tmp"}}']
    fake_llm = FakeStreamLLM(legacy_chunks)

    mock_exec_engine = MagicMock()
    mock_exec_engine.execute_tool = AsyncMock(return_value={"status": "ok", "items": []})

    orchestrator = PlannerOrchestrator(llm=fake_llm)
    orchestrator.agent_router = MagicMock(route_if_applicable=AsyncMock(return_value=None))
    orchestrator.context_service = MagicMock(build_context=AsyncMock(return_value=("", [], {})))
    orchestrator.memory.get_history = MagicMock(return_value=[])
    orchestrator.memory.add_message = MagicMock()
    orchestrator.execution_engine = mock_exec_engine

    emitted_events = []
    async for raw_event in orchestrator.run_stream("lista", llm=fake_llm):
        emitted_events.append(json.loads(raw_event))

    tool_events = [e for e in emitted_events if e.get("type") == "tool"]
    assert len(tool_events) == 1
    assert tool_events[0]["tool"] == "list_directory"
