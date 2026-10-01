import pytest
from app.utils.streaming_buffer import StreamingTokenBuffer

def test_streaming_token_buffer_single_chunk_without_tokens():
    buf = StreamingTokenBuffer()
    mapping = {"[NIF_1]": "12345678Z"}
    out = buf.feed("Texto simple sin corchetes.", mapping)
    assert out == "Texto simple sin corchetes."

def test_streaming_token_buffer_token_split_across_chunks():
    buf = StreamingTokenBuffer()
    mapping = {"[NIF_1]": "12345678Z", "[IMPORTE_1]": "1.500,00 €"}

    # Chunk 1: llega hasta la apertura parcial del token
    out1 = buf.feed("El NIF es [N", mapping)
    assert out1 == "El NIF es "  # Retiene '[N'

    # Chunk 2: completa el token y abre otro parcialmente
    out2 = buf.feed("IF_1] y el total es [IMPO", mapping)
    assert out2 == "12345678Z y el total es "

    # Chunk 3: completa el segundo token
    out3 = buf.feed("RTE_1]. Fin.", mapping)
    assert out3 == "1.500,00 €. Fin."

def test_streaming_token_buffer_unmatched_brackets_flushed():
    buf = StreamingTokenBuffer()
    mapping = {"[NIF_1]": "12345678Z"}
    # Corchete que no es token
    out1 = buf.feed("Ver lista [1, 2, 3] completa", mapping)
    assert out1 == "Ver lista [1, 2, 3] completa"

def test_streaming_token_buffer_flush_at_end():
    buf = StreamingTokenBuffer()
    mapping = {"[NIF_1]": "12345678Z"}
    out1 = buf.feed("Termina en [NIF_1]", mapping)
    assert "12345678Z" in out1
    remaining = buf.flush(mapping)
    assert remaining == ""
