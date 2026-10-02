"""
Tests de integración para el endpoint SSE de chat en streaming (Spec 029 - US2).
Valida:
1. Petición POST /chat con stream=True devuelve media_type text/event-stream.
2. Petición POST /chat/stream devuelve media_type text/event-stream y emite chunks data: {...}.
"""
import pytest
from unittest.mock import patch
from starlette.requests import Request
from fastapi.responses import StreamingResponse
from app.api.routes import chat_endpoint, ChatRequest


@pytest.mark.asyncio
async def test_post_chat_with_stream_flag():
    async def mock_run_stream(*args, **kwargs):
        yield '{"type": "chunk", "text": "Hola mundo"}'
        yield '{"type": "chat", "response": "Hola mundo"}'

    with patch("app.domain.planner_orchestrator.PlannerOrchestrator.run_stream", side_effect=mock_run_stream):
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat",
            "headers": [(b"host", b"testserver"), (b"x-api-key", b"test_api_key_default")],
        }
        async def dummy_receive():
            return {"type": "http.disconnect"}
        request = Request(scope, receive=dummy_receive)
        req = ChatRequest(message="Hola", stream=True)
        response = await chat_endpoint(req, request)

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        full_text = "".join(chunks)

        assert "data: " in full_text
        assert "Hola mundo" in full_text
        assert "data: [DONE]\n\n" in full_text


@pytest.mark.asyncio
async def test_post_chat_stream_endpoint():
    async def mock_run_stream(*args, **kwargs):
        yield '{"type": "chunk", "text": "Respuesta stream"}'

    with patch("app.domain.planner_orchestrator.PlannerOrchestrator.run_stream", side_effect=mock_run_stream):
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/chat/stream",
            "headers": [(b"host", b"testserver"), (b"x-api-key", b"test_api_key_default")],
        }
        async def dummy_receive():
            return {"type": "http.disconnect"}
        request = Request(scope, receive=dummy_receive)
        req = ChatRequest(message="Test stream")
        response = await chat_endpoint(req, request)

        assert isinstance(response, StreamingResponse)
        assert response.media_type == "text/event-stream"

        chunks = []
        async for chunk in response.body_iterator:
            chunks.append(chunk)
        full_text = "".join(chunks)

        assert "data: " in full_text
        assert "Respuesta stream" in full_text
        assert "data: [DONE]\n\n" in full_text
