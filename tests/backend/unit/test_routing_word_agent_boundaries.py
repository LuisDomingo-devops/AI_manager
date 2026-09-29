import pytest
import re
from unittest.mock import MagicMock
from app.domain.planner_orchestrator import SpecializedAgentRouter

@pytest.mark.asyncio
async def test_word_routing_does_not_trigger_on_password():
    """
    Verifica la sección 11 del Discovery Contract:
    'word' in msg_lower NO debe provocar que 'password' se interprete como Word.
    Mensajes como 'genera un password' o 'crea un password seguro' NO deben delegar a WordAgent.
    """
    mock_memory = MagicMock()
    mock_logger = MagicMock()
    router = SpecializedAgentRouter(memory=mock_memory)

    # Mensajes trampa que contienen "word" como subcadena dentro de "password"
    trap_messages = [
        "genera un password",
        "crea un password seguro",
        "resetea mi password",
        "olvidé mi password",
    ]

    for msg in trap_messages:
        # Actualmente esto delega a WordAgent porque "word" in "password" y "genera"/"crea" in msg
        # Con la corrección, debe devolver None (no enrutar a WordAgent)
        result = await router.route_if_applicable(
            user_message=msg,
            session_id="test_session",
            client_id="test_client",
            logger=mock_logger
        )
        assert result is None, (
            f"Falso positivo en enrutamiento: el mensaje '{msg}' no debe enrutar a WordAgent pero devolvió: {result}"
        )
