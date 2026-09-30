"""Cliente de Pasarela Cloudflare Worker para inferencia de Gemini.

Aísla las llamadas a modelos de lenguaje con circuit breaker, timeouts estrictos
y degradación elegante hacia estado offline.
"""

import os
import logging
from typing import Optional
import httpx

from app.infrastructure.ai_gateway.contract import (
    IAIGatewayClient,
    GatewayResponse,
)
from app.infrastructure.ai_gateway.circuit_breaker import CircuitBreaker

logger = logging.getLogger("ai_gateway_client")


class CloudflareAIGatewayClient(IAIGatewayClient):
    """Cliente HTTP asíncrono para el Cloudflare Worker de Alfonso AI Konta."""

    def __init__(
        self,
        worker_url: Optional[str] = None,
        license_token: Optional[str] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        self.worker_url = (
            worker_url
            or os.getenv("CLOUDFLARE_WORKER_URL", "https://alfonso-worker.test.workers.dev")
        ).rstrip("/") + "/"
        self.license_token = license_token or os.getenv("ALFONSO_CLIENT_SECRET", "")
        self.circuit_breaker = circuit_breaker or CircuitBreaker()

    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: str = "gemini-3.1-flash-lite",
        timeout_seconds: float = 15.0,
    ) -> GatewayResponse:
        """Envía la solicitud a Cloudflare Worker con protección de fallos."""
        if not self.circuit_breaker.can_execute():
            return GatewayResponse(
                success=False,
                is_fallback=True,
                error_code="CIRCUIT_OPEN",
                error_message="Servicio de IA temporalmente pausado tras fallos reiterados de conexión.",
            )

        payload = {
            "model": model,
            "apiVersion": "v1beta",
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        }
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        headers = {
            "Content-Type": "application/json",
            "X-Alfonso-License-Token": self.license_token,
        }

        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                res = await client.post(self.worker_url, json=payload, headers=headers)

                if res.status_code == 200:
                    self.circuit_breaker.record_success()
                    data = res.json()
                    candidates = data.get("candidates", [])
                    text = ""
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        text = "".join(p.get("text", "") for p in parts)
                    
                    tokens_used = data.get("usageMetadata", {}).get("totalTokenCount", 0)
                    return GatewayResponse(
                        success=True,
                        text_content=text,
                        tokens_used=tokens_used,
                        is_fallback=False,
                    )
                elif res.status_code == 429:
                    self.circuit_breaker.record_failure()
                    return GatewayResponse(
                        success=False,
                        error_code="QUOTA_EXCEEDED",
                        error_message="Límite de cuota del modelo de IA alcanzado. Por favor, intente más tarde.",
                    )
                elif res.status_code == 401:
                    self.circuit_breaker.record_failure()
                    return GatewayResponse(
                        success=False,
                        error_code="UNAUTHORIZED",
                        error_message="Token de autenticación con la pasarela de IA no válido.",
                    )
                else:
                    self.circuit_breaker.record_failure()
                    return GatewayResponse(
                        success=False,
                        error_code="GATEWAY_ERROR",
                        error_message=f"Error en el servidor de inferencia (HTTP {res.status_code}).",
                    )

        except httpx.TimeoutException:
            self.circuit_breaker.record_failure()
            logger.warning(f"Timeout de {timeout_seconds}s excedido conectando a Cloudflare Worker.")
            return GatewayResponse(
                success=False,
                error_code="TIMEOUT",
                error_message="Tiempo de espera agotado al conectar con el asistente de IA.",
            )
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Error de red comunicando con pasarela de IA: {e}")
            return GatewayResponse(
                success=False,
                error_code="NETWORK_ERROR",
                error_message=f"No se pudo conectar con el servicio de IA: {str(e)}",
            )
