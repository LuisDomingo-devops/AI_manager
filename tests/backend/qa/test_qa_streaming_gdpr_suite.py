import pytest
import time
from app.utils.streaming_buffer import StreamingTokenBuffer
from app.domain.schemas import AnonymizationSession

def test_qa_streaming_buffer_latency_under_2ms_per_chunk():
    buffer = StreamingTokenBuffer()
    mapping = {f"[TOKEN_{i}]": f"VALOR_REAL_{i}" for i in range(100)}

    chunks = [
        "Fragmento de texto con [TOK",
        "EN_1] y más contenido [TOKEN",
        "_2] validado sin problemas."
    ] * 50

    start = time.perf_counter()
    for chunk in chunks:
        buffer.feed(chunk, mapping)
    buffer.flush(mapping)
    total_time = (time.perf_counter() - start) * 1000
    avg_per_chunk = total_time / len(chunks)

    # Requisito de la spec: latencia < 2ms por chunk
    assert avg_per_chunk < 2.0, f"Latencia excesiva: {avg_per_chunk:.4f} ms/chunk"

def test_qa_streaming_session_memory_purged():
    session = AnonymizationSession()
    session.register_entity("12345678Z", "NIF", 0, 9)
    assert len(session.token_to_value_map) == 1

    # Simular purga al finalizar el stream
    session.purge()
    assert len(session.token_to_value_map) == 0
    assert len(session.value_to_token_map) == 0
    assert len(session.entities) == 0
