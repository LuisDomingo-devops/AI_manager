"""Contrato de la Pasarela de IA (Cloudflare Worker).

Define la interfaz del cliente HTTPS saliente y los modelos de respuesta
con soporte para degradación elegante y circuit breaker.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AIGatewayRequestPayload(BaseModel):
    """Estructura enviada a la pasarela de Cloudflare Worker."""
    model: str = "gemini-3.1-flash-lite"
    apiVersion: str = "v1beta"
    systemInstruction: Optional[Dict[str, Any]] = None
    contents: list = Field(default_factory=list)
    generationConfig: Dict[str, Any] = Field(
        default_factory=lambda: {"temperature": 0.2, "maxOutputTokens": 2048}
    )


class GatewayResponse(BaseModel):
    """Resultado normalizado de una invocación de inferencia."""
    success: bool
    text_content: str = ""
    tokens_used: int = 0
    is_fallback: bool = False
    error_code: Optional[str] = None  # "TIMEOUT", "QUOTA_EXCEEDED", "UNAUTHORIZED", "OFFLINE"
    error_message: Optional[str] = None


class IAIGatewayClient(ABC):
    """Cliente de escritorio para interactuar con la pasarela Cloudflare Worker."""

    @abstractmethod
    async def generate_content(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        model: str = "gemini-3.1-flash-lite",
        timeout_seconds: float = 15.0,
    ) -> GatewayResponse:
        """Envía la petición a la pasarela con timeout y degradación elegante."""
        pass
