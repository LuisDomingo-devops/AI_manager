"""Pruebas de integración de circuit breaker y resiliencia de la pasarela de IA (T021 - TDD).

Valida que tras múltiples fallos consecutivos el circuito se abra y responda inmediatamente
con degradación elegante sin esperar timeouts de red.
"""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest

from app.infrastructure.ai_gateway.client import CloudflareAIGatewayClient
from app.infrastructure.ai_gateway.circuit_breaker import CircuitBreaker


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_consecutive_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_time_seconds=60)
    client = CloudflareAIGatewayClient(
        worker_url="https://alfonso-worker.test.workers.dev",
        license_token="token",
        circuit_breaker=cb
    )
    
    mock_err_resp = MagicMock()
    mock_err_resp.status_code = 500
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_err_resp
        
        # Simular 3 caídas consecutivas (500 Internal Server Error)
        for _ in range(3):
            res = await client.generate_content("intento")
            assert res.success is False
            
        assert cb.state == "OPEN"
        
        # El cuarto intento debe retornar degradación de inmediato sin llamar a la red
        mock_post.reset_mock()
        res4 = await client.generate_content("intento bloqueado por circuit breaker")
        assert res4.success is False
        assert res4.is_fallback is True
        assert res4.error_code == "CIRCUIT_OPEN"
        mock_post.assert_not_called()
