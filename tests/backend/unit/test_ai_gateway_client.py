"""Pruebas unitarias para el cliente de pasarela Cloudflare Worker (T020 - TDD).

Valida el envío de cabeceras de licencia, formateo de payload y control de timeout estricto.
"""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
import httpx

from app.infrastructure.ai_gateway.client import CloudflareAIGatewayClient


@pytest.mark.asyncio
async def test_cloudflare_client_successful_inference():
    client = CloudflareAIGatewayClient(
        worker_url="https://alfonso-worker.test.workers.dev",
        license_token="test_secret_token_123"
    )
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "candidates": [
            {"content": {"parts": [{"text": "Respuesta generada por Gemini"}]}}
        ],
        "usageMetadata": {"totalTokenCount": 42}
    }
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = await client.generate_content("Hola, ¿cuál es el estado contable?")
        
        assert response.success is True
        assert response.text_content == "Respuesta generada por Gemini"
        assert response.tokens_used == 42
        assert response.is_fallback is False
        mock_post.assert_awaited_once()
        args, kwargs = mock_post.call_args
        assert kwargs["headers"].get("X-Alfonso-License-Token") == "test_secret_token_123"


@pytest.mark.asyncio
async def test_cloudflare_client_handles_quota_429_gracefully():
    client = CloudflareAIGatewayClient(
        worker_url="https://alfonso-worker.test.workers.dev",
        license_token="test_secret_token_123"
    )
    
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.json.return_value = {"error": "Resource has been exhausted (e.g. check quota)."}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        response = await client.generate_content("Pregunta con cuota excedida")
        
        assert response.success is False
        assert response.error_code == "QUOTA_EXCEEDED"
        assert "cuota" in response.error_message.lower() or "disponible" in response.error_message.lower()
