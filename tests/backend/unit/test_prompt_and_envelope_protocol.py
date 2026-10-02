"""
Tests unitarios para la sincronización unificada entre el generador de prompts y LLMDecisionEnvelope (Spec 029 - US1).
Valida:
1. Que generate_tool_prompt emita exclusivamente el esquema canónico {"type": "tool_call", "tool_name": "...", "tool_args": {...}}
2. Que extract_json_robust instancie LLMDecisionEnvelope tipado.
3. Normalización preventiva ante payloads legacy {"tool": "...", "args": {...}}.
4. Tratamiento limpio de bloques CoT (<think>...</think>).
"""
import pytest
from app.domain.prompt_generator import generate_tool_prompt
from app.domain.schemas import LLMDecisionEnvelope, IntentType, ProtocolError
from app.infrastructure.adapters.llm_client import extract_json_robust


class TestPromptGeneratorProtocol:
    """Verificación de la especificación de salida en el prompt de sistema."""

    def test_tool_prompt_contains_canonical_envelope_format(self):
        prompt = generate_tool_prompt()
        # Debe contener la especificación canónica
        assert '"type": "tool_call"' in prompt or '"type":"tool_call"' in prompt
        assert '"tool_name"' in prompt
        assert '"tool_args"' in prompt

    def test_tool_prompt_eliminates_obsolete_format(self):
        prompt = generate_tool_prompt()
        # No debe contener el formato antiguo como formato canónico
        assert '{"tool":"TOOL_NAME","args":' not in prompt
        assert '{"tool": "TOOL_NAME", "args":' not in prompt


class TestExtractJsonRobustParsing:
    """Verificación del parsing de inferencia con LLMDecisionEnvelope."""

    def test_extract_canonical_tool_call(self):
        raw = '{"type": "tool_call", "tool_name": "create_directory", "tool_args": {"path": "/tmp/test"}}'
        envelope = extract_json_robust(raw)
        assert isinstance(envelope, LLMDecisionEnvelope)
        assert envelope.type == IntentType.tool_call
        assert envelope.tool_name == "create_directory"
        assert envelope.tool_args == {"path": "/tmp/test"}

    def test_extract_canonical_message(self):
        raw = '{"type": "message", "message": "El saldo actual es de 1.500 €"}'
        envelope = extract_json_robust(raw)
        assert isinstance(envelope, LLMDecisionEnvelope)
        assert envelope.type == IntentType.message
        assert envelope.message == "El saldo actual es de 1.500 €"

    def test_extract_with_cot_thinking_block(self):
        raw = (
            "<think>\nEl usuario quiere crear un directorio.\nUsaré create_directory.\n</think>\n"
            '{"type": "tool_call", "tool_name": "create_directory", "tool_args": {"path": "/home/user/docs"}}'
        )
        envelope = extract_json_robust(raw)
        assert isinstance(envelope, LLMDecisionEnvelope)
        assert envelope.type == IntentType.tool_call
        assert envelope.tool_name == "create_directory"
        assert envelope.tool_args["path"] == "/home/user/docs"

    def test_extract_with_markdown_fences(self):
        raw = '```json\n{"type": "tool_call", "tool_name": "list_directory", "tool_args": {"path": "."}}\n```'
        envelope = extract_json_robust(raw)
        assert isinstance(envelope, LLMDecisionEnvelope)
        assert envelope.type == IntentType.tool_call
        assert envelope.tool_name == "list_directory"

    def test_legacy_format_normalization(self):
        """Si un modelo legacy responde con {"tool": "...", "args": {...}}, normalizar de forma preventiva."""
        raw = '{"tool": "get_balance_situacion", "args": {"year": 2026}}'
        envelope = extract_json_robust(raw)
        assert isinstance(envelope, LLMDecisionEnvelope)
        assert envelope.type == IntentType.tool_call
        assert envelope.tool_name == "get_balance_situacion"
        assert envelope.tool_args == {"year": 2026}

    def test_invalid_json_raises_protocol_error(self):
        with pytest.raises(ProtocolError):
            extract_json_robust("No soy un json")
