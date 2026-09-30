"""Pruebas de integración para el despacho aislado de agentes (T028 - TDD).

Valida que el despacho dinámico delega tareas asíncronas y retorna AgentResponse
sin acoplarse a regex estáticas del orquestador.
"""

import pytest

from app.domain.agents.base import IAgentPlugin, AgentContext, AgentResponse
from app.domain.agents.registry import AgentRegistry


class MathMockAgent(IAgentPlugin):
    @property
    def agent_id(self) -> str:
        return "math_agent"

    @property
    def description(self) -> str:
        return "Agente de cálculos matemáticos"

    def can_handle(self, user_message: str, context: AgentContext) -> bool:
        return any(op in user_message.lower() for op in ["calcular", "suma", "multiplica"])

    async def handle(self, user_message: str, context: AgentContext) -> AgentResponse:
        return AgentResponse(
            agent_id=self.agent_id,
            success=True,
            content="Cálculo completado: 42",
            structured_data={"result": 42}
        )


@pytest.mark.asyncio
async def test_dynamic_agent_dispatch_executes_isolated():
    registry = AgentRegistry()
    registry.register(MathMockAgent())
    
    context = AgentContext(tenant_id="test_tenant")
    msg = "Por favor calcula la suma de la factura"
    
    handler = registry.find_handler(msg, context)
    assert handler is not None
    
    resp = await handler.handle(msg, context)
    assert resp.success is True
    assert resp.agent_id == "math_agent"
    assert resp.structured_data == {"result": 42}
