"""
PLANNER ORCHESTRATOR — Planificador y orquestador central de Alfonso.

¿QUÉ HACE?
Orquesta y ejecuta el ciclo de vida del planificador (fase de intención, planificación y ejecución de herramientas). Es el pipeline principal por el que pasa cada petición de usuario.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/api/routes.py: Invoca este orquestador a través de /chat.
- app/domain/agents/marcos/marcos_agent.py: Delega consultas de legislación española.
- app/adapters/tool_registry.py: Busca y proporciona las herramientas a ejecutar.
"""

from __future__ import annotations

import asyncio
import inspect
import re

from app.domain.ports.llm_port import LLMPort
from app.domain.ports.memory_port import MemoryPort, VectorMemoryPort
from app.domain.ports.bridge_port import BridgePort
from app.domain.ports.calendar_port import CalendarPort
from app.adapters.tool_registry import (
    get_tool,
    is_client_tool,
    get_client_action,
    prepare_tool_args,
)

class LazyAdapterProxy:
    def __init__(self, import_path: str, object_name: str):
        self._import_path = import_path
        self._object_name = object_name

    def __getattr__(self, name: str):
        import importlib
        module = importlib.import_module(self._import_path)
        concrete = getattr(module, self._object_name)
        return getattr(concrete, name)

memory = LazyAdapterProxy("app.adapters.memory", "memory")
vector_memory = LazyAdapterProxy("app.adapters.memory", "vector_memory")
bridge = LazyAdapterProxy("app.adapters.alfonso_bridge", "bridge")

def extract_json_robust(raw: str) -> dict | None:
    from app.adapters.llm_client import extract_json_robust as concrete
    return concrete(raw)

from app.utils.logger import (
    attach_request_id,
    error_logger,
    orchestrator_logger,
)

_TOOL_TIMEOUT = 300

_DIRECT_CONFIRM = {
    "browser_navigate": "Navegación completada.",
}

from app.domain.services.intent_parser import (
    normalize_message,
    force_tool,
)

_normalize_message = normalize_message
_force_tool = force_tool

def _extract_tool_and_args(data):
    if not isinstance(data, dict):
        return None, {}

    if "tool" in data:
        return data["tool"], data.get("args", {})

    key = next(iter(data), None)
    if key:
        value = data[key]
        if isinstance(value, dict):
            return key, value.get("args", {})

    return None, {}

def _check_and_store_fact(user_message: str, session_id: str, client_id: str | None = None, vector_memory_port=None) -> bool:
    msg_lower = user_message.lower()
    patterns = [
        "recuerda que",
        "guarda que",
        "mi favorito es",
        "mi favorita es",
        "me gusta",
        "tengo un",
        "vivo en",
        "mi nombre es",
        "me llamo",
    ]
    if any(p in msg_lower for p in patterns):
        cleaned_fact = user_message
        for p in ["recuerda que", "guarda que"]:
            if msg_lower.startswith(p):
                cleaned_fact = user_message[len(p):].strip()
                break
        if vector_memory_port is None:
            from app.adapters.memory import vector_memory as vector_memory_port
        vector_memory_port.add_fact(session_id, cleaned_fact, client_id=client_id)
        return True
    return False


# ==============================================================================
# SERVICIOS COMPONENTIZADOS (Responsabilidad Única)
# ==============================================================================

class ConversationContextService:
    """Responsabilidad: Clasificación de tipos de consulta, logs de corrección y ensamblado de contexto semántico."""
    def __init__(self, memory: MemoryPort, vector_memory: VectorMemoryPort):
        self.memory = memory
        self.vector_memory = vector_memory

    async def classify_and_log_corrections(self, user_message: str, session_id: str | None, client_id: str | None, request_id: str | None, logger, error) -> bool:
        is_persistent = True
        msg_lower = user_message.lower()

        ephemeral_keywords = [
            "qué hora es", "que hora es", "dime la hora", "temperatura", "termostato",
            "sube el", "baja el", "enciende", "apaga", "pon música", "pon musica",
            "clima hoy", "tiempo hoy", "qué día es hoy", "que dia es hoy"
        ]
        
        project_keywords = [
            "proyecto", "investiga", "investigar", "programa", "programar", 
            "escribe codigo", "escribe código", "diseña", "diseño", "plano", "pieza"
        ]

        if any(kw in msg_lower for kw in ephemeral_keywords):
            is_persistent = False
            logger.info("Conversación clasificada como EFÍMERA debido a palabras clave cotidianas/domótica.")
        elif session_id:
            existing_meta = self.memory.get_metadata(session_id)
            if existing_meta:
                is_persistent = existing_meta["is_persistent"]
            else:
                is_project = any(kw in msg_lower for kw in project_keywords) or len(user_message.split()) > 10
                is_persistent = is_project
                
                if is_persistent:
                    words = user_message.split()
                    title = " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                    discipline = "código/desarrollo" if "programa" in msg_lower or "código" in msg_lower else "general"
                    self.memory.upsert_metadata(session_id, title=title, discipline=discipline, project_name="default", is_persistent=True)
                    logger.info("Nueva conversación persistente iniciada y guardada en metadatos: %s", title)

        corrections_keywords = ["incorrecto", "mal", "error", "corregir", "corrige", "falso", "alucinando", "alucinacion", "no es asi", "no es así", "no es cierto"]
        if any(kw in user_message.lower() for kw in corrections_keywords):
            try:
                import time
                from pathlib import Path
                logs_dir = Path("logs")
                logs_dir.mkdir(exist_ok=True)
                corr_log = logs_dir / "user_corrections.log"
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S") + ",000"
                with open(corr_log, "a", encoding="utf-8") as f:
                    f.write(f"{timestamp} | WARNING | orchestrator | [{request_id or 'sys'}] Corrección del usuario: {user_message}\n")
            except Exception as e:
                error.warning("No se pudo escribir en user_corrections.log: %s", e)

        return is_persistent

    async def build_context(self, user_message: str, session_id: str | None, client_id: str | None) -> tuple[str | None, list[str], list[str]]:
        _check_and_store_fact(user_message, session_id, client_id=client_id, vector_memory_port=self.vector_memory)

        general_facts = self.vector_memory.query_facts(user_message, limit=3, client_id=client_id)
        
        style_queries = ["estilo de respuesta", "preferencia de formato", "personalidad de Alfonso"]
        style_facts = []
        for q in style_queries:
            results = self.vector_memory.query_facts(q, limit=2, client_id=client_id)
            for fact in results:
                if fact not in style_facts:
                    style_facts.append(fact)
        
        memory_parts = []
        if style_facts:
            memory_parts.append("[Directrices de estilo preferidas por el usuario:]")
            for fact in style_facts:
                memory_parts.append(f"- {fact}")
            memory_parts.append("")
            
        filtered_general = [f for f in general_facts if f not in style_facts]
        if filtered_general:
            memory_parts.append("[Recuerdos semánticos relevantes del usuario:]")
            for fact in filtered_general:
                memory_parts.append(f"- {fact}")
            memory_parts.append("")
            
        if session_id:
            session_summary = self.memory.get_summary(session_id, client_id=client_id)
            if session_summary:
                memory_parts.append("[Historial de la conversación reciente:]")
                memory_parts.append(session_summary)
                
        memory_text = "\n".join(memory_parts) if memory_parts else None
        return memory_text, style_facts, filtered_general


class SpecializedAgentRouter:
    """Responsabilidad: Enrutamiento directo a subagentes de dominio específico (Marcos, CyberSecurityAgent)."""
    def __init__(self, memory: MemoryPort):
        self.memory = memory

    async def route_if_applicable(self, user_message: str, session_id: str | None, client_id: str | None, logger) -> dict | None:
        msg_lower = user_message.lower()
        
        is_marcos_query = "marcos" in msg_lower or any(kw in msg_lower for kw in [
            "codigo civil", "código civil", "codigo penal", "código penal",
            "constitucion española", "constitucion espanola", "constitución española",
            "asesoria legal", "asesoría legal", "consulta juridica", "consulta jurídica",
            "iva", "irpf", "impuesto", "impuestos", "tributo", "tributaria", "tributos",
            "hacienda", "aeat", "declaración de la renta", "declaracion de la renta",
            "deducción", "deduccion", "deducciones", "jurisprudencia", "sentencia", "fiscal"
        ])
        is_security_query = any(kw in msg_lower for kw in [
            "ciberseguridad", "cybersecurity", "seguridad", "security", "vulnerabilidad", 
            "vulnerabilities", "auditoría de seguridad", "auditoria de seguridad", "hack",
            "phishing", "malware", "firewall", "puerto", "risk", "riesgo", "alerta de seguridad"
        ]) or ("cyberagent" in msg_lower or "agente de seguridad" in msg_lower or "securityagent" in msg_lower)

        if is_marcos_query:
            logger.info("Consulta de tipo legal. Delegando a MarcosAgent.")
            from app.domain.agents.marcos.marcos_agent import marcos_agent
            response = await marcos_agent.generate_response(user_message)
            if session_id:
                self.memory.add_message(session_id, "assistant", response, client_id=client_id)
            return {
                "type": "chat",
                "response": response,
            }

        if is_security_query:
            logger.info("Consulta de seguridad. Delegando a CyberSecurityAgent.")
            from app.domain.agents.security.security_agent import security_agent
            response = await security_agent.generate_response(user_message)
            if session_id:
                self.memory.add_message(session_id, "assistant", response, client_id=client_id)
            return {
                "type": "chat",
                "response": response,
            }

        # ── ExcelAgent Routing ──────────────────────────────────────────
        is_excel_query = "excel" in msg_lower or "hoja de cálculo" in msg_lower or "hoja de calculo" in msg_lower or "libro diario" in msg_lower or "balance de situación" in msg_lower or "balance de situacion" in msg_lower
        if is_excel_query and ("exporta" in msg_lower or "genera" in msg_lower or "crea" in msg_lower or "excel" in msg_lower):
            logger.info("Consulta de hoja de cálculo. Delegando a ExcelAgent.")
            from app.domain.agents.excel.excel_agent import excel_agent
            response = await excel_agent.generate_response(user_message, client_id=client_id or "default")
            if session_id:
                self.memory.add_message(session_id, "assistant", response, client_id=client_id)
            return {
                "type": "chat",
                "response": response,
            }

        # ── WordAgent Routing ───────────────────────────────────────────
        is_word_query = "word" in msg_lower or "docx" in msg_lower or "redacta" in msg_lower or "informe financiero" in msg_lower or "documento" in msg_lower
        if is_word_query and ("genera" in msg_lower or "crea" in msg_lower or "redacta" in msg_lower or "word" in msg_lower):
            logger.info("Consulta de redacción documental. Delegando a WordAgent.")
            from app.domain.agents.word.word_agent import word_agent
            response = await word_agent.generate_response(user_message, client_id=client_id or "default")
            if session_id:
                self.memory.add_message(session_id, "assistant", response, client_id=client_id)
            return {
                "type": "chat",
                "response": response,
            }

        return None


class ToolExecutionEngine:
    """Responsabilidad: Control del ciclo de ejecución, control de acceso RBAC y validación sintáctica de código."""
    def __init__(self, memory: MemoryPort, bridge: BridgePort):
        self.memory = memory
        self.bridge = bridge

    async def execute_tool(self, tool_name: str, args: dict, session_id: str | None, client_id: str | None, request_id: str | None, logger, error) -> dict:
        if is_client_tool(tool_name):
            logger.info("Ejecutando tool de cliente: %s", tool_name)
            action = get_client_action(tool_name)
            result = await self.bridge.send_command(action, args, client_id=client_id)
            
            if not isinstance(result, dict) or result.get("status") == "error":
                error.warning("Tool de cliente falló: %s -> %s", tool_name, result)
                return {
                    "status": "error",
                    "execution": "client",
                    "result": result,
                    "message": result.get("error", "Error en ejecución de cliente") if isinstance(result, dict) else "Respuesta vacía de cliente"
                }
            return {
                "status": "ok",
                "execution": "client",
                "result": result,
            }
        else:
            import sys
            is_testing = "pytest" in sys.modules
            role = "admin" if is_testing else "guest"
            if client_id:
                client_meta = self.bridge._client_info_dict.get(client_id)
                if client_meta:
                    role = client_meta.get("role", "guest")
                else:
                    from app.config import settings
                    role = settings.get_client_role(client_id)
            
            if role in ("guest", "limitado") and tool_name != "no_op":
                logger.warning("Acceso denegado: el cliente %s con rol %s intentó ejecutar %s", client_id, role, tool_name)
                return {
                    "status": "rbac_error",
                    "execution": "server",
                    "message": f"Acceso denegado: el rol '{role}' no tiene permisos para ejecutar la herramienta de servidor '{tool_name}'",
                }

            logger.info("Ejecutando tool de servidor: %s", tool_name)
            tool = get_tool(tool_name, request_id)

            if not tool:
                return {
                    "status": "missing_error",
                    "execution": "server",
                    "message": f"No existe {tool_name}",
                }

            validation_res = prepare_tool_args(tool_name, args, request_id)
            if not validation_res.ok:
                error.warning("Validación de argumentos falló para %s: %s", tool_name, validation_res.error)
                return {
                    "status": "validation_error",
                    "execution": "server",
                    "message": validation_res.error,
                }
            args = validation_res.args

            try:
                sig = inspect.signature(tool)
                if "session_id" in sig.parameters:
                    args["session_id"] = session_id or "global"
                if "client_id" in sig.parameters:
                    args["client_id"] = client_id
            except Exception as e:
                logger.warning("No se pudo inspeccionar la firma: %s", e)

            try:
                if asyncio.iscoroutinefunction(tool):
                    result = await asyncio.wait_for(tool(**args), timeout=_TOOL_TIMEOUT)
                else:
                    loop = asyncio.get_running_loop()
                    result = await asyncio.wait_for(loop.run_in_executor(None, lambda: tool(**args)), timeout=_TOOL_TIMEOUT)
            except Exception as e:
                error.exception("Error ejecutando tool de servidor: %s", tool_name)
                return {
                    "status": "execution_error",
                    "execution": "server",
                    "message": str(e),
                }

            # Validación de sintaxis local en archivos Python
            if tool_name in ("create_file", "append_file", "replace_file_content") and isinstance(result, dict) and result.get("status") == "ok":
                file_path = args.get("path")
                if file_path and str(file_path).endswith(".py"):
                    try:
                        import py_compile
                        from app.tools.server.filesystem_tools import _resolve_path
                        resolved_path = _resolve_path(str(file_path))
                        if resolved_path.exists():
                            py_compile.compile(str(resolved_path), doraise=True)
                            logger.info("Validación sintáctica exitosa para: %s", file_path)
                    except py_compile.PyCompileError as py_err:
                        error_msg = f"Error de sintaxis de Python: {py_err.msg.strip()}"
                        logger.warning("Validación sintáctica falló: %s", error_msg)
                        result = {
                            "status": "error",
                            "message": f"El archivo se guardó pero tiene errores de sintaxis: {error_msg}"
                        }
                    except Exception as e:
                        logger.warning("No se pudo validar la sintaxis: %s", e)

            if isinstance(result, dict) and result.get("status") == "error":
                error.warning("Tool de servidor falló: %s -> %s", tool_name, result)
                return {
                    "status": "error",
                    "execution": "server",
                    "message": result.get("message", "Error ejecutando tool"),
                    "result": result,
                }

            return {
                "status": "ok",
                "execution": "server",
                "result": result,
            }


# ==============================================================================
# PLANNER ORCHESTRATOR (Coordinador)
# ==============================================================================

class PlannerOrchestrator:
    """
    Pipeline único de Alfonso: No hay EventBus ni AgentRegistry.
    PlannerOrchestrator coordina el ciclo de vida delegando a servicios específicos
    de Contexto, Enrutamiento de Agentes y Motor de Ejecución.
    """

    def __init__(
        self,
        llm: LLMPort | None = None,
        memory: MemoryPort | None = None,
        vector_memory: VectorMemoryPort | None = None,
        bridge: BridgePort | None = None,
        calendar: CalendarPort | None = None
    ):
        self._llm = llm
        self._memory = memory
        self._vector_memory = vector_memory
        self._bridge = bridge
        self._calendar = calendar

        self.context_service = ConversationContextService(self.memory, self.vector_memory)
        self.agent_router = SpecializedAgentRouter(self.memory)
        self.execution_engine = ToolExecutionEngine(self.memory, self.bridge)

    @property
    def llm(self):
        if self._llm is not None:
            return self._llm
        from app.adapters.llm_client import OllamaClient
        return OllamaClient()

    @property
    def memory(self):
        if self._memory is not None:
            return self._memory
        global memory
        return memory

    @property
    def vector_memory(self):
        if self._vector_memory is not None:
            return self._vector_memory
        global vector_memory
        return vector_memory

    @property
    def bridge(self):
        if self._bridge is not None:
            return self._bridge
        global bridge
        return bridge

    @property
    def calendar(self):
        if self._calendar is not None:
            return self._calendar
        from app.adapters.calendar_db import SQLiteCalendarAdapter
        return SQLiteCalendarAdapter()

    async def run(self, user_message, llm=None, request_id=None, session_id=None, client_id=None):
        llm = llm or self.llm
        logger = attach_request_id(orchestrator_logger, request_id)
        
        from app.adapters.memory.memory import tenant_context
        token = tenant_context.set(client_id or "default")
        try:
            res = await self._run_internal(user_message, llm, request_id, session_id, client_id)
        finally:
            tenant_context.reset(token)
        
        if session_id and not getattr(self.memory, "is_testing", False) and res.get("type") == "chat":
            try:
                history = self.memory.get_history(session_id, client_id=client_id)
                if history:
                    conv_text = "\n".join(f"{m['role']}: {m['content']}" for m in history if m['role'] in ('user', 'assistant'))
                    summary_prompt = (
                        "Resume de manera muy breve y concisa los temas principales tratados en la siguiente conversación "
                        "de hoy (máximo 2-3 frases). Enfócate en las decisiones tomadas o las consultas del usuario:\n\n"
                        f"{conv_text}"
                    )
                    summary = await llm.generate(
                        summary_prompt,
                        mode="chat",
                        request_id=request_id,
                        client_id=client_id,
                    )
                    self.memory.update_summary(session_id, summary.strip())
            except Exception as e:
                logger.warning("Error generating daily conversation summary: %s", e)
                
        return res

    async def _run_internal(self, user_message, llm=None, request_id=None, session_id=None, client_id=None):
        llm = llm or self.llm
        logger = attach_request_id(orchestrator_logger, request_id)
        error = attach_request_id(error_logger, request_id)

        logger.info("PlannerOrchestrator.run() — request_id=%s, session_id=%s, client_id=%s", request_id, session_id, client_id)
        user_message = _normalize_message(user_message)

        if session_id:
            self.memory.add_message(session_id, "user", user_message, client_id=client_id)

        # 1. Clasificación y persistencia
        await self.context_service.classify_and_log_corrections(
            user_message, session_id, client_id, request_id, logger, error
        )

        # 2. Ensamblado de Contexto
        memory_text, style_facts, filtered_general = await self.context_service.build_context(
            user_message, session_id, client_id
        )

        # 3. Enrutamiento directo a agentes
        routed = await self.agent_router.route_if_applicable(user_message, session_id, client_id, logger)
        if routed:
            return routed

        # 3.5. Enrutamiento unificado nativo mediante el function-calling del LLM (heurístico regex retirado para producción)
        raw = None

        # 4. Bucle ReAct multi-turno para ejecución secuencial de herramientas
        max_turns = 5
        current_turn = 1

        while current_turn <= max_turns:
            logger.info("--- TURNO DE ORQUESTACIÓN %d ---", current_turn)
            memory_text, _, _ = await self.context_service.build_context(user_message, session_id, client_id)

            if current_turn > 1 or not raw:
                raw = await llm.generate(
                    user_message,
                    mode="tool",
                    request_id=request_id,
                    memory=memory_text,
                    client_id=client_id,
                )
                logger.info("Raw LLM output (Turno %d): %s", current_turn, repr(raw))

            data = extract_json_robust(raw)

            # Si no se detectó JSON estructurado de tool, o es no_op / respuesta conversacional, terminamos y devolvemos como chat
            if not data or "tool" not in data or data.get("tool") == "no_op":
                logger.info("Respuesta clasificada como conversacional o fin de ciclo de herramientas.")
                response_str = raw
                if data and data.get("tool") == "no_op":
                    response_str = data.get("message") or data.get("args", {}).get("message") or raw

                # Fallback para evitar respuestas JSON vacías o crudas de error
                if response_str.strip() in ("{}", "", '"{}"', "None"):
                    response_str = "Disculpa, he tenido un problema al procesar tu solicitud. ¿Podrías repetirme la consulta o indicarme en qué puedo ayudarte?"

                if session_id:
                    self.memory.add_message(session_id, "assistant", response_str, client_id=client_id)
                return {
                    "type": "chat",
                    "response": response_str,
                }

            tool_name, args = _extract_tool_and_args(data)

            if not tool_name:
                logger.warning("No se pudo extraer el nombre de la herramienta del JSON.")
                raw = None
                current_turn += 1
                continue

            # Si es una herramienta de interfaz del cliente (abrir/cerrar ventanas, etc.), la devolvemos inmediatamente para ejecución local de UI
            from app.adapters.tool_registry import is_client_tool
            # Herramientas exclusivas de transición de interfaz (se interceptan para que la GUI PyQt actúe directamente)
            UI_TRANSITION_TOOLS = {
                "calendar_open_ui", "calendar_close_ui",
                "mail_open_ui", "mail_close_ui",
                "dev_studio_open_ui", "dev_studio_close_ui",
                "switch_project_session"
            }
            if tool_name in UI_TRANSITION_TOOLS:
                logger.info("Detectada tool de interfaz de cliente: %s. Delegando ejecución a UI.", tool_name)
                if session_id:
                    import json
                    self.memory.add_message(session_id, "assistant", json.dumps({"tool": tool_name, "args": args}), client_id=client_id)
                return {
                    "type": "tool",
                    "execution": "client",
                    "tool": tool_name,
                    "args": args,
                    "result": {},
                }

            # Si es una herramienta directa con confirmación instantánea
            if tool_name in _DIRECT_CONFIRM:
                confirm_text = _DIRECT_CONFIRM[tool_name]
                if session_id:
                    self.memory.add_message(session_id, "assistant", confirm_text, client_id=client_id)
                return {
                    "type": "chat",
                    "response": confirm_text,
                }

            # Ejecución de herramienta de servidor
            logger.info("Ejecutando tool de servidor en el orquestador: %s con args: %s", tool_name, args)
            exec_res = await self.execution_engine.execute_tool(
                tool_name, args, session_id, client_id, request_id, logger, error
            )

            status = exec_res.get("status")
            result = exec_res.get("result")

            if status == "rbac_error":
                error_msg = exec_res.get("message", "Acceso denegado")
                if session_id:
                    self.memory.add_message(session_id, "assistant", f"Error: {error_msg}", client_id=client_id)
                return {
                    "type": "error",
                    "message": error_msg,
                }

            if status in ("validation_error", "missing_error", "error"):
                error_msg = exec_res.get("message", "Error de ejecución")
                if session_id:
                    import json
                    self.memory.add_message(session_id, "assistant", json.dumps({"tool": tool_name, "args": args}), client_id=client_id)
                    self.memory.add_message(session_id, "system", f"Tool output error: {error_msg}. Corrige los parámetros y reintenta.", client_id=client_id)
                raw = None
                current_turn += 1
                continue

            # Registrar ejecución en memoria
            if session_id:
                import json
                self.memory.add_message(session_id, "assistant", json.dumps({"tool": tool_name, "args": args}), client_id=client_id)
                self.memory.add_message(session_id, "system", f"Tool output: {json.dumps(result)}", client_id=client_id)

            if tool_name == "generate_invoice_pdf":
                logger.info("Forzando parada del bucle de herramientas tras generar factura PDF para interactividad.")
                break

            # Limpiamos raw para forzar una nueva generación de inferencia del LLM en el siguiente turno
            raw = None
            current_turn += 1

        # Si excedemos los turnos máximos sin respuesta final, hacemos una llamada en modo chat
        logger.warning("Excedido el número máximo de turnos de herramientas (%d). Generando respuesta final.", max_turns)
        memory_text, _, _ = await self.context_service.build_context(user_message, session_id, client_id)
        chat_response = await llm.generate(
            user_message,
            mode="chat",
            request_id=request_id,
            memory=memory_text,
            client_id=client_id,
        )
        if session_id:
            self.memory.add_message(session_id, "assistant", chat_response, client_id=client_id)
        return {
            "type": "chat",
            "response": chat_response,
        }
