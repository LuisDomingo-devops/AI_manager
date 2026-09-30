"""Prueba de QA: Tolerancia y confinamiento de excepciones en agentes (T029 - TDD).

Valida que si un agente falla estrepitosamente (ZeroDivisionError, RuntimeError),
la excepción queda confinada y no tumba el proceso ni la aplicación de escritorio.
"""

import pytest

from app.domain.agents.base import IAgentPlugin, AgentContext, AgentResponse
from app.domain.agents.registry import AgentRegistry


class CrashingMockAgent(IAgentPlugin):
    @property
    def agent_id(self) -> str:
        return "crashing_agent"

    @property
    def description(self) -> str:
        return "Agente con fallo crítico simulado"

    def can_handle(self, user_message: str, context: AgentContext) -> bool:
        return "romper" in user_message.lower()

    async def handle(self, user_message: str, context: AgentContext) -> AgentResponse:
        # Simular fallo interno no previsto
        raise ZeroDivisionError("División por cero en cálculo de datos de hoja")


@pytest.mark.asyncio
async def test_agent_registry_safe_dispatch_confines_unhandled_exceptions():
    registry = AgentRegistry()
    registry.register(CrashingMockAgent())
    
    context = AgentContext(tenant_id="test_tenant")
    msg = "Quiero romper el cálculo"
    
    # safe_dispatch debe capturar la excepción y devolver AgentResponse con success=False
    resp = await registry.safe_dispatch(msg, context)
    
    assert resp is not None
    assert resp.success is False
    assert resp.agent_id == "crashing_agent"
    assert "División por cero" in (resp.error_message or "")
