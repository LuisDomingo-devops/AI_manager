import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.domain.planner_orchestrator import SpecializedAgentRouter

@pytest.mark.asyncio
async def test_orchestrator_routing_integrity_differentiates_word_and_password():
    """
    Verifica la discriminación estricta de rutas en SpecializedAgentRouter:
    1. Mensajes sobre 'password' NO deben invocar a word_agent.generate_response.
    2. Mensajes genuinos sobre 'Word'/'docx' SÍ deben invocar a word_agent.generate_response.
    """
    mock_memory = MagicMock()
    mock_logger = MagicMock()
    router = SpecializedAgentRouter(memory=mock_memory)

    with patch("app.domain.agents.word.word_agent.word_agent.generate_response", new_callable=AsyncMock) as mock_word_gen:
        mock_word_gen.return_value = "Documento generado exitosamente"

        # 1. Petición de contraseña con verbos de generación
        res_pwd = await router.route_if_applicable(
            user_message="genera un nuevo password para el usuario",
            session_id="session_pwd_01",
            client_id="client_test",
            logger=mock_logger
        )
        assert res_pwd is None, (
            f"'genera un nuevo password...' no debe ser capturado por WordAgent, resultado: {res_pwd}"
        )
        assert mock_word_gen.call_count == 0, (
            "word_agent.generate_response NO debe ser invocado para una consulta de password"
        )

        # 2. Petición genuina de Word
        res_word = await router.route_if_applicable(
            user_message="genera un documento en formato Word con el resumen",
            session_id="session_word_01",
            client_id="client_test",
            logger=mock_logger
        )
        assert res_word is not None, "La consulta sobre Word debe ser enrutada"
        assert res_word.get("type") == "chat"
        assert mock_word_gen.call_count == 1, (
            "word_agent.generate_response SÍ debe ser invocado exactamente 1 vez para la consulta de Word"
        )
