import pytest
from unittest.mock import patch
from app.infrastructure.adapters.llm_client import LLMClient

async def fake_stream_generator():
    yield "Respuesta: El cliente [N"
    yield "IF_1] tiene saldo de [IMPO"
    yield "RTE_1]."

@pytest.mark.asyncio
async def test_llm_client_stream_chat_detokenizes_stream_on_the_fly():
    client = LLMClient()
    messages = [{"role": "user", "content": "NIF 12345678Z con 1.500,00 €"}]

    with patch.object(client, "stream_chat") as mock_stream:
        # Simulamos la integración del envoltorio de stream
        from app.utils.streaming_buffer import StreamingTokenBuffer
        buffer = StreamingTokenBuffer()
        mapping = {"[NIF_1]": "12345678Z", "[IMPORTE_1]": "1.500,00 €"}

        accumulated = []
        async for chunk in fake_stream_generator():
            accumulated.append(buffer.feed(chunk, mapping))
        accumulated.append(buffer.flush(mapping))

        full_output = "".join(accumulated)
        assert "12345678Z" in full_output
        assert "1.500,00 €" in full_output
        assert "[NIF_1]" not in full_output
        assert "[IMPORTE_1]" not in full_output
