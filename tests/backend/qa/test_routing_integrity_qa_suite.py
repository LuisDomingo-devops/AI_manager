import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.domain.planner_orchestrator import SpecializedAgentRouter

@pytest.mark.asyncio
async def test_routing_integrity_qa_matrix():
    """
    Suite de QA para discriminación léxica de rutas:
    Prueba una matriz de expresiones con homónimos, subcadenas accidentales y términos ofimáticos legítimos.
    """
    mock_memory = MagicMock()
    mock_logger = MagicMock()
    router = SpecializedAgentRouter(memory=mock_memory)

    with patch("app.domain.agents.word.word_agent.word_agent.generate_response", new_callable=AsyncMock) as mock_word_gen:
        mock_word_gen.return_value = "Generado"

        # Casos que NO deben activar WordAgent (falsos positivos potenciales)
        negative_cases = [
            "genera una nueva password para el usuario",
            "crea un password robusto con símbolos",
            "dame un sword de hierro",
            "resuelve este crossword para mí",
            "escribe el foreword del libro",
            "forward de puertos en el router",
            "cuál es la password del wifi",
        ]

        for msg in negative_cases:
            res = await router.route_if_applicable(
                user_message=msg,
                session_id="session_qa_neg",
                client_id="client_qa",
                logger=mock_logger
            )
            assert res is None, f"Falso positivo detectado para '{msg}': resultado={res}"

        assert mock_word_gen.call_count == 0, "WordAgent no debió ser llamado para ningún caso negativo"

        # Casos legítimos que SÍ deben activar WordAgent
        positive_cases = [
            "genera un documento word con el balance",
            "crea un archivo docx con el informe financiero",
            "redacta un documento con las conclusiones",
            "crea una plantilla word para contratos",
        ]

        for idx, msg in enumerate(positive_cases, start=1):
            res = await router.route_if_applicable(
                user_message=msg,
                session_id=f"session_qa_pos_{idx}",
                client_id="client_qa",
                logger=mock_logger
            )
            assert res is not None, f"Falso negativo: '{msg}' debió activar WordAgent"
            assert res.get("type") == "chat"

        assert mock_word_gen.call_count == len(positive_cases), (
            f"WordAgent debió ser llamado {len(positive_cases)} veces, llamado: {mock_word_gen.call_count}"
        )
