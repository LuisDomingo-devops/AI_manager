"""
Tests unitarios para el protocolo LLM estructurado (Spec 013).
Verifican el contrato de LLMDecisionEnvelope, IntentType, ProtocolError
y la función extract_json_robust de forma aislada.

FR-001: Contrato explícito y validable
FR-002: Sin fallback JSONDecodeError
FR-003: Malformed → ProtocolError
FR-004: Tool errors distintos de protocol errors
FR-005: Conversacional NUNCA interpretado como tool_call
"""
import pytest
from pydantic import ValidationError

from app.domain.schemas import LLMDecisionEnvelope, IntentType, ProtocolError
from app.infrastructure.adapters.llm_client import extract_json_robust


class TestIntentTypeEnum:
    """FR-001: El enum IntentType debe cubrir todos los tipos requeridos."""

    def test_has_message_type(self):
        assert IntentType.message == "message"

    def test_has_tool_call_type(self):
        assert IntentType.tool_call == "tool_call"

    def test_has_clarification_type(self):
        assert IntentType.clarification == "clarification"

    def test_has_confirmation_required_type(self):
        assert IntentType.confirmation_required == "confirmation_required"

    def test_has_error_type(self):
        assert IntentType.error == "error"

    def test_total_types_count(self):
        """Exactamente 5 tipos definidos en el contrato."""
        assert len(IntentType) == 5


class TestLLMDecisionEnvelopeSchema:
    """FR-001: LLMDecisionEnvelope es un contrato Pydantic válido."""

    def test_valid_message_envelope(self):
        env = LLMDecisionEnvelope(type=IntentType.message, message="Hola")
        assert env.type == IntentType.message
        assert env.message == "Hola"
        assert env.tool_name is None
        assert env.tool_args is None

    def test_valid_tool_call_envelope(self):
        env = LLMDecisionEnvelope(
            type=IntentType.tool_call,
            tool_name="create_invoice",
            tool_args={"client_id": "C001", "amount": 1000.0},
        )
        assert env.type == IntentType.tool_call
        assert env.tool_name == "create_invoice"
        assert env.tool_args["amount"] == 1000.0

    def test_valid_clarification_envelope(self):
        env = LLMDecisionEnvelope(
            type=IntentType.clarification,
            message="¿Te refieres a agosto o septiembre?",
        )
        assert env.type == IntentType.clarification

    def test_valid_confirmation_required_envelope(self):
        env = LLMDecisionEnvelope(
            type=IntentType.confirmation_required,
            message="¿Confirmas el envío del modelo 303?",
        )
        assert env.type == IntentType.confirmation_required

    def test_valid_error_envelope(self):
        env = LLMDecisionEnvelope(type=IntentType.error, error_code="UNKNOWN_COMMAND")
        assert env.type == IntentType.error
        assert env.error_code == "UNKNOWN_COMMAND"

    def test_invalid_type_raises_validation_error(self):
        """Un tipo no reconocido debe fallar en validación Pydantic."""
        with pytest.raises((ValidationError, ValueError)):
            LLMDecisionEnvelope(type="invented_type", message="test")

    def test_missing_type_raises_validation_error(self):
        """Sin campo 'type', el modelo Pydantic debe rechazarlo."""
        with pytest.raises(ValidationError):
            LLMDecisionEnvelope(message="sin tipo")


class TestProtocolError:
    """FR-003: ProtocolError tiene contrato claro con message y raw_output."""

    def test_protocol_error_is_exception(self):
        assert issubclass(ProtocolError, Exception)

    def test_protocol_error_stores_message(self):
        err = ProtocolError("JSON inválido", "{broken}")
        assert err.message == "JSON inválido"

    def test_protocol_error_stores_raw_output(self):
        raw = "{broken json"
        err = ProtocolError("parse failed", raw)
        assert err.raw_output == raw

    def test_protocol_error_str_representation(self):
        err = ProtocolError("Failed to parse", "{}")
        assert "Failed to parse" in str(err)


class TestExtractJsonRobust:
    """FR-002/FR-003/FR-005: extract_json_robust sin fallbacks JSONDecodeError."""

    def test_extracts_message_intent_from_clean_json(self):
        raw = '{"type": "message", "message": "Buenos días"}'
        env = extract_json_robust(raw)
        assert isinstance(env, LLMDecisionEnvelope)
        assert env.type == IntentType.message
        assert env.message == "Buenos días"

    def test_extracts_tool_call_intent_from_clean_json(self):
        raw = '{"type": "tool_call", "tool_name": "get_balance", "tool_args": {"account": "ES91"}}'
        env = extract_json_robust(raw)
        assert env.type == IntentType.tool_call
        assert env.tool_name == "get_balance"

    def test_strips_markdown_code_fences(self):
        """El extractor debe manejar bloques ```json ... ```."""
        raw = '```json\n{"type": "message", "message": "test"}\n```'
        env = extract_json_robust(raw)
        assert env.type == IntentType.message

    def test_empty_string_raises_protocol_error(self):
        """Respuesta vacía → ProtocolError, NO texto plano al usuario."""
        with pytest.raises(ProtocolError):
            extract_json_robust("")

    def test_none_like_empty_raises_protocol_error(self):
        """Whitespace only → ProtocolError."""
        with pytest.raises(ProtocolError):
            extract_json_robust("   ")

    def test_plain_text_without_json_raises_protocol_error(self):
        """FR-003/FR-005: texto plano sin JSON → ProtocolError, NUNCA message."""
        with pytest.raises(ProtocolError):
            extract_json_robust("Hola, soy una respuesta de texto plano sin estructura")

    def test_broken_json_raises_protocol_error(self):
        """JSON malformado → ProtocolError."""
        with pytest.raises(ProtocolError) as exc_info:
            extract_json_robust('{"type": "tool_call", "tool_name":')
        assert exc_info.value.raw_output is not None

    def test_json_with_unknown_intent_type_raises_protocol_error(self):
        """JSON con 'type' inventado → ProtocolError (ValidationError de Pydantic)."""
        with pytest.raises(ProtocolError):
            extract_json_robust('{"type": "invented_intent", "message": "test"}')

    def test_conversational_text_never_becomes_tool_call(self):
        """FR-005: texto conversacional no puede ser tipo tool_call."""
        raw = '{"type": "message", "message": "Por favor, crea la factura"}'
        env = extract_json_robust(raw)
        # Nunca debe ser tool_call
        assert env.type != IntentType.tool_call
        assert env.type == IntentType.message

    def test_protocol_error_has_raw_output_field(self):
        """El ProtocolError debe exponer el raw_output original para debugging."""
        bad_raw = '{"type": "broken'
        with pytest.raises(ProtocolError) as exc_info:
            extract_json_robust(bad_raw)
        assert exc_info.value.raw_output is not None

    def test_tool_error_distinct_from_protocol_error(self):
        """FR-004: Un tool_call válido NO es un ProtocolError."""
        raw = '{"type": "tool_call", "tool_name": "send_invoice", "tool_args": {}}'
        # No debe lanzar ProtocolError
        env = extract_json_robust(raw)
        assert env.type == IntentType.tool_call
        # El error de herramienta es posterior (ejecución), no de protocolo
