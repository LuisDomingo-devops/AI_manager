import pytest
from unittest.mock import AsyncMock, patch
from app.infrastructure.adapters.llm_client import LLMClient
from app.domain.exceptions import AnonymizationFailureError

@pytest.mark.asyncio
async def test_llm_client_chat_sends_only_tokens_and_detokenizes():
    client = LLMClient()
    messages = [
        {"role": "user", "content": "Hola, transfiere 500,00 € a ES6621000418401234567891 para el NIF 12345678Z"}
    ]

    mock_response = "He preparado la transferencia de [IMPORTE_1] a la cuenta [IBAN_1] para [NIF_1]."

    with patch.object(client, "_call_gemini_api", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = (mock_response, 10, 20)

        res = await client.chat(messages)

        # Comprobar qué viajó en el payload hacia la API de Gemini
        called_messages = mock_call.call_args[0][0]
        sent_content = called_messages[0]["content"]

        assert "[IMPORTE_1]" in sent_content
        assert "[IBAN_1]" in sent_content
        assert "[NIF_1]" in sent_content
        assert "12345678Z" not in sent_content
        assert "ES6621000418401234567891" not in sent_content

        # Comprobar que el usuario recibe la respuesta final desanonimizada
        assert "500,00 €" in res
        assert "ES6621000418401234567891" in res
        assert "12345678Z" in res

@pytest.mark.asyncio
async def test_llm_client_chat_fail_closed_on_error():
    client = LLMClient()
    messages = [{"role": "user", "content": "NIF 12345678Z"}]

    with patch("app.utils.anonymizer.DataAnonymizer.anonymize", side_effect=Exception("Fallo forzado")):
        with patch.object(client, "_call_gemini_api", new_callable=AsyncMock) as mock_call:
            with pytest.raises(AnonymizationFailureError):
                await client.chat(messages)
            # Certificar que la llamada externa a Gemini NUNCA ocurrió
            mock_call.assert_not_called()
