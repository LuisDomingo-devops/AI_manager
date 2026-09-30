"""Pruebas unitarias para AgentRegistry (T027 - TDD).

Valida el registro, desregistro y descubrimiento dinámico de plugins de agentes.
"""

import pytest

from app.domain.agents.base import IAgentPlugin, AgentContext, AgentResponse
from app.domain.agents.registry import AgentRegistry


class DummyMockAgent(IAgentPlugin):
    @property
    def agent_id(self) -> str:
        return "dummy_agent"

    @property
    def description(self) -> str:
        return "Agente de prueba para tests unitarios"

    def can_handle(self, user_message: str, context: AgentContext) -> bool:
        return "dummy" in user_message.lower()

    async def handle(self, user_message: str, context: AgentContext) -> AgentResponse:
        return AgentResponse(
            agent_id=self.agent_id,
            success=True,
            content="Respuesta de dummy agent",
        )


def test_agent_registry_register_and_find():
    registry = AgentRegistry()
    agent = DummyMockAgent()
    
    registry.register(agent)
    context = AgentContext()
    
    handler = registry.find_handler("Por favor ejecuta dummy tarea", context)
    assert handler is not None
    assert handler.agent_id == "dummy_agent"


def test_agent_registry_unhandled_message_returns_none():
    registry = AgentRegistry()
    agent = DummyMockAgent()
    registry.register(agent)
    
    context = AgentContext()
    handler = registry.find_handler("Consulta no soportada sobre clima", context)
    assert handler is None


def test_agent_registry_unregister():
    registry = AgentRegistry()
    agent = DummyMockAgent()
    registry.register(agent)
    
    registry.unregister("dummy_agent")
    context = AgentContext()
    assert registry.find_handler("dummy tarea", context) is None
