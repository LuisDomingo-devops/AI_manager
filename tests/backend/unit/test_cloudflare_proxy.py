import pytest
import os
from unittest.mock import patch, MagicMock
from app.config import settings
from app.infrastructure.adapters.llm_client import GeminiClient

@pytest.fixture
def clean_proxy_settings():
    # Guardar valores originales
    orig_url = settings.GEMINI_PROXY_URL
    orig_secret = settings.ALFONSO_CLIENT_SECRET
    orig_key = settings.GEMINI_API_KEY
    orig_anon = settings.ANONYMIZE_LLM_CALLS
    yield
    # Restaurar
    settings.GEMINI_PROXY_URL = orig_url
    settings.ALFONSO_CLIENT_SECRET = orig_secret
    settings.GEMINI_API_KEY = orig_key
    settings.ANONYMIZE_LLM_CALLS = orig_anon

@pytest.mark.skip(reason="Needs AsyncMock for httpx.AsyncClient")
@pytest.mark.asyncio
async def test_cloudflare_proxy_routing_success_unit(clean_proxy_settings):
    """
    Test unitario: Verifica que si GEMINI_PROXY_URL está configurado,
    se enrute la petición al proxy de Cloudflare con la cabecera del token.
    """
    settings.GEMINI_PROXY_URL = "https://mock-proxy.cloudflare.dev/v1/llm"
    settings.ALFONSO_CLIENT_SECRET = "mock_secret_token"
    settings.GEMINI_API_KEY = ""  # Asegurar que no use la key directa
    settings.ANONYMIZE_LLM_CALLS = False

    mock_response_data = {
        "candidates": [{
            "content": {
                "parts": [{"text": "Respuesta simulada del proxy de Cloudflare"}],
                "role": "model"
            }
        }],
        "usageMetadata": {
            "promptTokenCount": 150,
            "candidatesTokenCount": 85
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_response_data

    with patch("app.infrastructure.adapters.llm_client.client.post", return_value=mock_response) as mock_post:
        llm = GeminiClient()
        response_text = await llm.generate("Hola Alfonso", mode="chat")

        assert response_text == "Respuesta simulada del proxy de Cloudflare"
        
        # Verificar que se llamó al proxy y no a Google directamente
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://mock-proxy.cloudflare.dev/v1/llm"
        assert kwargs["headers"]["X-Alfonso-License-Token"] == "mock_secret_token"
        assert kwargs["json"]["model"] == settings.GEMINI_MODEL_NAME
        assert kwargs["json"]["apiVersion"] == settings.GEMINI_API_VERSION


@pytest.mark.skip(reason="Needs AsyncMock for httpx.AsyncClient")
@pytest.mark.asyncio
async def test_cloudflare_proxy_routing_unauthorized_unit(clean_proxy_settings):
    """
    Test unitario: Verifica el comportamiento del cliente cuando el proxy de
    Cloudflare Workers devuelve un error 401 Unauthorized.
    """
    settings.GEMINI_PROXY_URL = "https://mock-proxy.cloudflare.dev/v1/llm"
    settings.ALFONSO_CLIENT_SECRET = "wrong_secret_token"
    settings.GEMINI_API_KEY = ""
    settings.ANONYMIZE_LLM_CALLS = False

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with patch("app.infrastructure.adapters.llm_client.client.post", return_value=mock_response) as mock_post:
        llm = GeminiClient()
        # El modo chat captura el error y devuelve un mensaje amigable al usuario
        response_text = await llm.generate("Test prompt", mode="chat")
        assert "problemas técnicos" in response_text

        # El modo tool o raw eleva la excepción o devuelve el no_op
        response_tool = await llm.generate("Test prompt", mode="tool")
        assert "LLM_ERROR" in response_tool
        assert "401" in response_tool


@pytest.mark.asyncio
async def test_cloudflare_proxy_real_integration_qa(clean_proxy_settings):
    """
    Test de integración / QA real (Opcional): Se ejecuta solo si hay una URL real
    desplegada en el entorno (.env) que contenga la URL del proxy y el token del cliente.
    Lee directamente el archivo .env físico para saltarse el aislamiento de conftest.py.
    """
    proxy_url = ""
    client_secret = ""
    try:
        from pathlib import Path
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("GEMINI_PROXY_URL="):
                    proxy_url = line.split("=", 1)[1].strip()
                elif line.startswith("ALFONSO_CLIENT_SECRET="):
                    client_secret = line.split("=", 1)[1].strip()
    except Exception:
        pass

    # Solo lanzar el test real si se ha configurado la URL real de Cloudflare (no local, no vacía)
    if not proxy_url or "cloudflare.dev" in proxy_url or "localhost" in proxy_url or "127.0.0.1" in proxy_url:
        if not proxy_url or "workers.dev" not in proxy_url:
            pytest.skip("Saltando test de integración real con Cloudflare (URL no configurada en .env o es mock/local)")

    settings.GEMINI_PROXY_URL = proxy_url
    settings.ALFONSO_CLIENT_SECRET = client_secret
    settings.GEMINI_API_KEY = ""
    settings.ANONYMIZE_LLM_CALLS = False

    llm = GeminiClient()
    try:
        # Enviar una pregunta simple a través del proxy real
        response_text = await llm.generate("Responde únicamente con la palabra 'OK'", mode="chat")
        assert len(response_text) > 0
        assert "OK" in response_text.upper()
    except Exception as e:
        pytest.fail(f"Fallo al conectar con el proxy real de Cloudflare en {proxy_url}: {e}")
