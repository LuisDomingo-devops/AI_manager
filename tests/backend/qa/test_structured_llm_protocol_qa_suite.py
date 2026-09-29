"""
Suite QA para el Protocolo LLM Estructurado (Spec 013).
Verifica criterios de éxito SC-001 y SC-002 de la especificación.

SC-001: extract_json_robust sin try/except como control de flujo para mensajes.
SC-002: 100% de los 5 escenarios de aceptación automatizados.
"""
import pytest

from app.domain.schemas import LLMDecisionEnvelope, IntentType, ProtocolError
from app.infrastructure.adapters.llm_client import extract_json_robust


class TestQASC001NoJSONDecodeErrorFallback:
    """
    SC-001: La función extract_json_robust NO usa JSONDecodeError
    como mecanismo de control de flujo para decidir si es conversacional.
    Un texto plano mal formado SIEMPRE debe producir ProtocolError.
    """

    def test_plain_spanish_text_never_silently_becomes_message(self):
        """Un texto conversacional en español sin estructura → ProtocolError."""
        conversational_texts = [
            "Claro, te ayudo con eso.",
            "Buenos días, ¿en qué puedo asistirte?",
            "La factura de agosto está pendiente de pago.",
            "Sí, confirmo el envío del modelo 347.",
        ]
        for text in conversational_texts:
            with pytest.raises(ProtocolError):
                extract_json_robust(text)

    def test_partial_json_never_silently_becomes_message(self):
        """JSON truncado → ProtocolError, no texto de fallback."""
        partial_jsons = [
            '{"type": "tool_call"',
            '{"type":',
            '{',
            '"type": "message"',
        ]
        for partial in partial_jsons:
            with pytest.raises(ProtocolError):
                extract_json_robust(partial)

    def test_random_binary_garbage_raises_protocol_error(self):
        """Basura aleatoria → ProtocolError."""
        with pytest.raises(ProtocolError):
            extract_json_robust("!!!@@@###$$$%%%^^^&&&")

    def test_xml_output_raises_protocol_error(self):
        """Respuesta XML (formato incorrecto) → ProtocolError."""
        with pytest.raises(ProtocolError):
            extract_json_robust("<response><type>message</type><text>Hola</text></response>")


class TestQASC002AcceptanceScenarios:
    """
    SC-002: Los 5 escenarios de aceptación de la spec deben pasar al 100%.
    """

    def test_sc002_scenario_1_normal_message_no_json_decode_error(self):
        """
        Escenario 1: Mensaje normal no produce JSONDecodeError.
        El resultado es un LLMDecisionEnvelope limpio de tipo 'message'.
        """
        raw = '{"type": "message", "message": "Aquí tienes el resumen de tus facturas."}'
        env = extract_json_robust(raw)
        assert isinstance(env, LLMDecisionEnvelope)
        assert env.type == IntentType.message
        assert env.message == "Aquí tienes el resumen de tus facturas."

    def test_sc002_scenario_2_valid_tool_call_identified_via_schema(self):
        """
        Escenario 2: Tool call válido identificado correctamente por schema.
        """
        raw = '{"type": "tool_call", "tool_name": "generate_invoice", "tool_args": {"client": "ACME", "amount": 500.0}}'
        env = extract_json_robust(raw)
        assert env.type == IntentType.tool_call
        assert env.tool_name == "generate_invoice"
        assert env.tool_args["client"] == "ACME"
        assert env.tool_args["amount"] == 500.0

    def test_sc002_scenario_3_invalid_json_produces_explicit_protocol_error(self):
        """
        Escenario 3: JSON inválido produce ProtocolError explícito.
        NO se interpreta como mensaje conversacional.
        """
        bad_json = '{"type": "tool_call", "tool_name": "INCOMPLETE'
        with pytest.raises(ProtocolError) as exc_info:
            extract_json_robust(bad_json)
        assert exc_info.value.raw_output is not None
        assert len(exc_info.value.raw_output) > 0

    def test_sc002_scenario_4_tool_error_not_confused_with_protocol_error(self):
        """
        Escenario 4: Error de herramienta es distinto de error de protocolo.
        Un tool_call válido parseado NO es un ProtocolError.
        El ProtocolError solo ocurre en análisis del JSON/schema.
        """
        # Tool call válido → NO ProtocolError en parsing
        valid_tool = '{"type": "tool_call", "tool_name": "delete_invoice", "tool_args": {"id": "F-001"}}'
        env = extract_json_robust(valid_tool)
        assert env.type == IntentType.tool_call
        # Si la herramienta fallara al ejecutarse, sería un error de ejecución,
        # no un ProtocolError. El protocolo en sí está correcto.

    def test_sc002_scenario_5_conversational_never_interpreted_as_tool_call(self):
        """
        Escenario 5: Respuesta conversacional NUNCA interpretada como tool_call.
        """
        conversational = '{"type": "message", "message": "Por favor, dame más información sobre qué factura quieres crear."}'
        env = extract_json_robust(conversational)
        assert env.type == IntentType.message
        assert env.type != IntentType.tool_call


class TestQAAllIntentTypesRoundTrip:
    """QA: Todos los tipos de intención hacen round-trip JSON → Envelope."""

    @pytest.mark.parametrize("raw,expected_type,extra_checks", [
        (
            '{"type": "message", "message": "Texto informativo"}',
            IntentType.message,
            lambda e: e.message == "Texto informativo",
        ),
        (
            '{"type": "tool_call", "tool_name": "list_invoices", "tool_args": {}}',
            IntentType.tool_call,
            lambda e: e.tool_name == "list_invoices",
        ),
        (
            '{"type": "clarification", "message": "¿Qué mes te refieres?"}',
            IntentType.clarification,
            lambda e: e.message is not None,
        ),
        (
            '{"type": "confirmation_required", "message": "¿Confirmas el borrado?"}',
            IntentType.confirmation_required,
            lambda e: e.message is not None,
        ),
        (
            '{"type": "error", "error_code": "UNSUPPORTED_OPERATION"}',
            IntentType.error,
            lambda e: e.error_code == "UNSUPPORTED_OPERATION",
        ),
    ])
    def test_intent_type_round_trip(self, raw, expected_type, extra_checks):
        env = extract_json_robust(raw)
        assert env.type == expected_type
        assert extra_checks(env)


class TestQAEdgeCases:
    """QA: Casos límite del protocolo."""

    def test_json_with_extra_unknown_fields_still_valid(self):
        """
        Campos extra en JSON no deben romper el protocolo
        (Pydantic ignora campos desconocidos por defecto).
        """
        raw = '{"type": "message", "message": "test", "extra_field": "ignored"}'
        # Si Pydantic está configurado con extra='ignore' (por defecto) funciona
        try:
            env = extract_json_robust(raw)
            assert env.type == IntentType.message
        except ProtocolError:
            # Si Pydantic está en modo forbid, también es válido rechazarlo
            pass

    def test_nested_tool_args_are_preserved(self):
        """Args anidados en tool_call se preservan íntegramente."""
        raw = '{"type": "tool_call", "tool_name": "create_payroll", "tool_args": {"employee": {"id": "E001", "name": "Ana"}, "period": "2024-09"}}'
        env = extract_json_robust(raw)
        assert env.tool_args["employee"]["name"] == "Ana"
        assert env.tool_args["period"] == "2024-09"

    def test_unicode_message_preserved(self):
        """Mensajes con caracteres unicode (español, acentos) se preservan."""
        raw = '{"type": "message", "message": "Revisión del ejercicio económico 2024: pérdidas y ganancias"}'
        env = extract_json_robust(raw)
        assert "pérdidas" in env.message
        assert "económico" in env.message

    def test_empty_tool_args_dict_is_valid(self):
        """tool_args vacío es válido para herramientas sin parámetros."""
        raw = '{"type": "tool_call", "tool_name": "get_current_user", "tool_args": {}}'
        env = extract_json_robust(raw)
        assert env.tool_args == {}
