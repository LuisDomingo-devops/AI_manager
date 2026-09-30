"""Proveedor de Inferencia Desacoplada para Alfonso AI Konta.

Centraliza la obtención del cliente de pasarela y ofrece mecanismos de contingencia.
"""

from typing import Optional
from app.infrastructure.ai_gateway.contract import IAIGatewayClient
from app.infrastructure.ai_gateway.client import CloudflareAIGatewayClient
from app.infrastructure.ai_gateway.circuit_breaker import CircuitBreaker

_global_gateway_client: Optional[IAIGatewayClient] = None
_shared_circuit_breaker: Optional[CircuitBreaker] = None


def get_ai_gateway_client() -> IAIGatewayClient:
    """Retorna la instancia global del cliente de pasarela con circuit breaker compartido."""
    global _global_gateway_client, _shared_circuit_breaker
    if _shared_circuit_breaker is None:
        _shared_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_time_seconds=60.0)
    if _global_gateway_client is None:
        _global_gateway_client = CloudflareAIGatewayClient(circuit_breaker=_shared_circuit_breaker)
    return _global_gateway_client


def reset_ai_gateway_client() -> None:
    """Restablece el cliente para pruebas unitarias."""
    global _global_gateway_client, _shared_circuit_breaker
    _global_gateway_client = None
    _shared_circuit_breaker = None
