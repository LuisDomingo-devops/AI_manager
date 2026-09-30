"""Contrato e Interfaces Base para Plugins de Agentes de Asistencia.

Permite registrar agentes dinámicamente y despachar tareas de forma desacoplada.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    """Contexto de ejecución inyectado en cada llamada a un agente."""
    tenant_id: str = "default"
    user_id: str = "local_user"
    session_id: str = "session_default"
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    """Respuesta estructurada devuelta por cualquier agente de asistencia."""
    agent_id: str
    success: bool
    content: str
    structured_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: float = 0.0


class IAgentPlugin(ABC):
    """Contrato base que deben implementar todos los agentes especializados."""

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Identificador único del agente (ej. 'excel_agent', 'cyber_agent')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Descripción funcional de las tareas que puede atender."""
        pass

    @abstractmethod
    def can_handle(self, user_message: str, context: AgentContext) -> bool:
        """Determina de forma autónoma si el mensaje del usuario corresponde a su especialidad."""
        pass

    @abstractmethod
    async def handle(self, user_message: str, context: AgentContext) -> AgentResponse:
        """Ejecuta la tarea de forma asíncrona y aislada."""
        pass
