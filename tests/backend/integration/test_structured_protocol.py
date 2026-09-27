import pytest
from unittest.mock import AsyncMock, patch

from app.domain.planner_orchestrator import PlannerOrchestrator
from app.infrastructure.adapters.llm_client import extract_json_robust
from app.domain.schemas import LLMDecisionEnvelope, IntentType, ProtocolError

@pytest.fixture
def orchestrator():
    return PlannerOrchestrator()

@pytest.mark.asyncio
async def test_extract_valid_conversational_message():
    """T003: Valid conversational message extracted cleanly"""
    raw_output = '```json\n{"type": "message", "message": "Hola, ¿cómo estás?"}\n```'
    
    envelope = extract_json_robust(raw_output)
    
    assert isinstance(envelope, LLMDecisionEnvelope)
    assert envelope.type == IntentType.message
    assert envelope.message == "Hola, ¿cómo estás?"

@pytest.mark.asyncio
async def test_extract_valid_tool_execution():
    """T007: Valid tool execution extracted cleanly"""
    raw_output = '{"type": "tool_call", "tool_name": "list_directory", "tool_args": {"path": "."}}'
    
    envelope = extract_json_robust(raw_output)
    
    assert isinstance(envelope, LLMDecisionEnvelope)
    assert envelope.type == IntentType.tool_call
    assert envelope.tool_name == "list_directory"
    assert envelope.tool_args == {"path": "."}

@pytest.mark.asyncio
async def test_extract_malformed_json_raises_protocol_error():
    """T010: Malformed JSON triggers ProtocolError"""
    raw_output = '{"type": "tool_call", "tool_name": "list_directory", "tool_args": ' # Missing closing braces
    
    with pytest.raises(ProtocolError) as exc_info:
        extract_json_robust(raw_output)
        
    assert "Failed to parse or validate JSON" in str(exc_info.value)
    assert exc_info.value.raw_output == raw_output.strip()

@pytest.mark.asyncio
async def test_extract_clarification_and_confirmation():
    """T013: Clarification and confirmation intents extracted cleanly"""
    # Clarification
    raw_output = '{"type": "clarification", "message": "¿Te refieres a la factura de agosto o julio?"}'
    envelope = extract_json_robust(raw_output)
    assert envelope.type == IntentType.clarification
    assert envelope.message == "¿Te refieres a la factura de agosto o julio?"

    # Confirmation
    raw_output2 = '{"type": "confirmation_required", "message": "¿Estás seguro de que deseas enviar el modelo 303?"}'
    envelope2 = extract_json_robust(raw_output2)
    assert envelope2.type == IntentType.confirmation_required
    assert envelope2.message == "¿Estás seguro de que deseas enviar el modelo 303?"
