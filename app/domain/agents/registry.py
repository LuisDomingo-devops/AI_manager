"""Registro y Despachador Dinámico de Plugins de Agentes de Asistencia.

Permite registrar agentes dinámicamente y ejecutar tareas aisladas con confinamiento de excepciones.
"""

import logging
import time
from typing import Dict, Optional

from app.domain.agents.base import IAgentPlugin, AgentContext, AgentResponse

logger = logging.getLogger("agent_registry")


class AgentRegistry:
    """Registro desacoplado para descubrimiento y despacho dinámico de agentes."""

    def __init__(self):
        self._plugins: Dict[str, IAgentPlugin] = {}

    def register(self, plugin: IAgentPlugin) -> None:
        """Registra un nuevo agente en el sistema sin reiniciar el orquestador."""
        self._plugins[plugin.agent_id] = plugin
        logger.info(f"Agente registrado: {plugin.agent_id} ({plugin.description})")

    def unregister(self, agent_id: str) -> None:
        """Retira un agente del sistema dinámicamente."""
        removed = self._plugins.pop(agent_id, None)
        if removed:
            logger.info(f"Agente retirado: {agent_id}")

    def find_handler(self, user_message: str, context: AgentContext) -> Optional[IAgentPlugin]:
        """Localiza el primer plugin capacitado para atender la solicitud."""
        for plugin in self._plugins.values():
            try:
                if plugin.can_handle(user_message, context):
                    return plugin
            except Exception as e:
                logger.error(f"Error evaluando can_handle en {plugin.agent_id}: {e}")
        return None

    async def safe_dispatch(self, user_message: str, context: AgentContext) -> Optional[AgentResponse]:
        """Despacha la petición capturando cualquier excepción no prevista."""
        handler = self.find_handler(user_message, context)
        if not handler:
            return None

        start_time = time.perf_counter()
        try:
            resp = await handler.handle(user_message, context)
            resp.execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return resp
        except Exception as e:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(f"Excepción no controlada en agente {handler.agent_id}: {e}", exc_info=True)
            return AgentResponse(
                agent_id=handler.agent_id,
                success=False,
                content="Se ha producido un error durante la ejecución de la tarea del asistente.",
                error_message=str(e),
                execution_time_ms=elapsed_ms,
            )

    def load_defaults(self) -> None:
        """Carga los agentes estándar del sistema si no están ya registrados."""
        if "excel_agent" not in self._plugins:
            try:
                from app.domain.agents.excel.excel_agent import excel_agent
                self.register(excel_agent)
            except Exception as e:
                logger.error(f"Error cargando excel_agent por defecto: {e}")

        if "word_agent" not in self._plugins:
            try:
                from app.domain.agents.word.word_agent import word_agent
                self.register(word_agent)
            except Exception as e:
                logger.error(f"Error cargando word_agent por defecto: {e}")

        if "cyber_agent" not in self._plugins:
            try:
                from app.domain.agents.security.security_agent import security_agent
                self.register(security_agent)
            except Exception as e:
                logger.error(f"Error cargando security_agent por defecto: {e}")


# Instancia singleton para uso en el orquestador
default_agent_registry = AgentRegistry()
default_agent_registry.load_defaults()
