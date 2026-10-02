"""
LLM CLIENT — Cliente del modelo de lenguaje (Gemini).

¿QUÉ HACE?
Gestiona la comunicación con el servidor Gemini local para generar texto, completar chats, estructurar JSON y precalentar el modelo.

¿CUÁNDO LO HACE?
Siempre que el orquestador, router o agentes requieran capacidades cognitivas de inferencia del LLM.

¿CÓMO LO HACE?
Formateando payloads HTTP compatibles con la API `/api/chat` de Gemini y llamándolos con app.infrastructure.adapters.http_client.py.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app.infrastructure.adapters.http_client.py (provee el cliente HTTP subyacente para las peticiones)
- app/domain/planner_orchestrator.py (usa este cliente para planificar y responder en el chat)
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path          
from app.config import settings
from app.infrastructure.adapters.http_client import client
from app.infrastructure.adapters.tool_registry import get_tool
from app.domain.prompt_generator import generate_tool_prompt, get_client_context_str
from app.utils.logger import attach_request_id, llm_logger, error_logger, app_logger
# ---------------------------------------------------------------------
# REGEX
# ---------------------------------------------------------------------

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)
_TOOL_INLINE = re.compile(r"^([a-z_]+)\s+(\{.*\})$", re.DOTALL | re.IGNORECASE)
_TOOL_SPLIT_COLON = re.compile(r"^([a-zA-Z_]+)\s*:\s*(\{.*\})$", re.DOTALL | re.IGNORECASE)
_TOOL_PLAIN_COLON = re.compile(r"^([a-zA-Z0-9_-]+)\s*:\s*(.+)$", re.DOTALL)
_TOOL_PLAIN_SPACE = re.compile(r"^([a-zA-Z0-9_-]+)\s+(.+)$", re.DOTALL)

# ---------------------------------------------------------------------
# UTIL
# ---------------------------------------------------------------------

def _get_current_date_str() -> str:
    ''' Esta función devuelve la fecha y hora actual en español, 
    en el formato: "lunes, 1 de enero de 2024, 14:30" '''

    now = datetime.now()
    days = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    months = [
        "enero","febrero","marzo","abril","mayo","junio",
        "julio","agosto","septiembre","octubre","noviembre","diciembre",
    ]
    return f"{days[now.weekday()]}, {now.day} de {months[now.month - 1]} de {now.year}, {now.strftime('%H:%M')}"


from functools import lru_cache

@lru_cache(maxsize=8) # Este decorador almacena en caché los prompts generados para evitar recalcularlos repetidamente'''
def _read_prompt_file(path: str) -> str:
    ''' Lee el contenido de un archivo de prompt y lo devuelve como cadena.'''
    return Path(path).read_text(encoding="utf-8")


def load_prompt(path: str) -> str:
    ''' Carga un prompt desde un archivo y devuelve su contenido.'''
    try:
        return _read_prompt_file(path)
    except FileNotFoundError:
        error_logger.error("Prompt no encontrado en %s, usando fallback mínimo", path)
        return "Eres Alfonso. Responde de forma útil y concisa."


def get_system_prompt(mode: str, client_id: str | None = None) -> str:
    ''' Devuelve el prompt de sistema correspondiente al modo 
    especificado ("chat", "raw" o "tool"). '''
    if mode == "chat":
        template = load_prompt(settings.CHAT_PROMPT_PATH)
        try:
            client_ctx = get_client_context_str(client_id)
            template = template + "\n\n" + client_ctx
        except (KeyError, ValueError, AttributeError, OSError) as e:
            error_logger.warning("Fallo al obtener contexto del cliente para prompt del sistema: %s", e)
    elif mode == "raw":
        return "Eres un asistente de procesamiento de datos útil y preciso."
    else:
        chat_template = load_prompt(settings.CHAT_PROMPT_PATH)
        tool_template = generate_tool_prompt(client_id)
        
        protocol_instruction = """
DEBES DEVOLVER EXCLUSIVAMENTE UN OBJETO JSON VÁLIDO QUE CUMPLA CON ESTE ESQUEMA:
{
  "type": "message" | "tool_call" | "clarification" | "confirmation_required" | "error",
  "message": "...", // opcional, texto de tu respuesta, pregunta o aclaración
  "tool_name": "...", // requerido si type=tool_call
  "tool_args": {...}, // requerido si type=tool_call
  "error_code": "..." // opcional si type=error
}
NO DEBES INCLUIR NINGÚN TEXTO FUERA DEL JSON.
"""
        template = chat_template + "\n\n" + tool_template + "\n\n" + protocol_instruction
    return template.replace("{current_date}", _get_current_date_str())
# ---------------------------------------------------------------------
# VALIDACIÓN TOOL
# ---------------------------------------------------------------------

def format_tool_call(tool_name: str, tool_args: dict | None = None) -> dict:
    ''' Formatea una llamada a herramienta con el protocolo canónico LLMDecisionEnvelope. '''
    return {"type": "tool_call", "tool_name": tool_name, "tool_args": tool_args or {}}


def validate_tool_call(tool_call: dict) -> dict:
    ''' Valida la estructura de la llamada a la herramienta y
    devuelve un diccionario con el nombre de la herramienta y sus 
    argumentos. Soporta tanto el formato canónico (tool_name/tool_args)
    como el formato legacy (tool/args). '''
    if not isinstance(tool_call, dict):
        return {
            "tool": "no_op", "args": {"message": "Invalid tool format"},
            "tool_name": "no_op", "tool_args": {"message": "Invalid tool format"}
        }

    tool_name = tool_call.get("tool_name") or tool_call.get("tool")
    args = tool_call.get("tool_args") if "tool_args" in tool_call else tool_call.get("args", {})

    tool = get_tool(tool_name)

    if tool is None:
        return {
            "tool": "no_op", "args": {"message": f"Tool no existe: {tool_name}"},
            "tool_name": "no_op", "tool_args": {"message": f"Tool no existe: {tool_name}"}
        }

    if not isinstance(args, dict):
        return {
            "tool": "no_op", "args": {"message": "Args inválidos"},
            "tool_name": "no_op", "tool_args": {"message": "Args inválidos"}
        }

    return {
        "tool": tool_name, "args": args,
        "tool_name": tool_name, "tool_args": args
    }


# ---------------------------------------------------------------------
# EXTRACTOR
# ---------------------------------------------------------------------
import json
import re

def extract_json_robust(raw: str):
    ''' Extrae y valida la respuesta del LLM según el protocolo estructurado. '''
    from app.domain.schemas import LLMDecisionEnvelope, IntentType, ProtocolError
    
    if not raw:
        raise ProtocolError("Empty response from LLM", "")

    raw = raw.strip()

    # Log thinking block content if present (CoT)
    think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL | re.IGNORECASE)
    if think_match:
        thinking_text = think_match.group(1).strip()
        llm_logger.info("Thought (CoT): %s", thinking_text)

    clean = _THINK_BLOCK.sub("", raw).strip()
    
    m = _JSON_BLOCK.search(clean)
    if m:
        clean = m.group(1)

    try:
        data = json.loads(clean)
        if not isinstance(data, dict):
            raise ProtocolError("Parsed JSON is not an object", raw)

        # Normalización preventiva de formato legacy: {"tool": "...", "args": {...}}
        if "type" not in data:
            if "tool" in data:
                data["type"] = IntentType.tool_call.value
                data["tool_name"] = data.get("tool")
                data["tool_args"] = data.get("args") or {}
            elif "message" in data:
                data["type"] = IntentType.message.value
            else:
                raise ProtocolError("Missing 'type' field in LLM decision", raw)
        elif data.get("type") in ("tool_call", IntentType.tool_call):
            if "tool_name" not in data and "tool" in data:
                data["tool_name"] = data.get("tool")
            if "tool_args" not in data and "args" in data:
                data["tool_args"] = data.get("args") or {}

        return LLMDecisionEnvelope(**data)
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Failed to parse or validate JSON: {str(e)}", raw)
    except ProtocolError:
        raise
    except Exception as e:
        raise ProtocolError(f"Failed to parse or validate JSON: {str(e)}", raw)

# ---------------------------------------------------------------------
# CLIENTE
# ---------------------------------------------------------------------

from app.domain.ports.llm_port import LLMPort

class GeminiClient(LLMPort):

    async def _call_gemini_api(self, messages: list[dict[str, str]], system_prompt: str | None = None, temperature: float = 0.7) -> tuple[str, int, int]:
        """Llamada directa mediante HTTP a la API oficial de Gemini 1.5 Flash."""
        system_instr_parts = []
        contents = []

        if system_prompt:
            system_instr_parts.append({"text": system_prompt})

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "") or ""
            if role == "system":
                system_instr_parts.append({"text": content})
            else:
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
            }
        }
        if system_instr_parts:
            payload["systemInstruction"] = {
                "parts": system_instr_parts
            }

        headers = {}
        if not settings.GEMINI_PROXY_URL:
            raise RuntimeError("GEMINI_PROXY_URL no está configurado. La conexión directa a la API no está permitida.")
        
        url = settings.GEMINI_PROXY_URL
        headers["X-Alfonso-License-Token"] = settings.ALFONSO_CLIENT_SECRET
        payload["model"] = settings.GEMINI_MODEL_NAME
        payload["apiVersion"] = settings.GEMINI_API_VERSION
        
        import asyncio
        for attempt in range(4):
            response = await client.post(url, json=payload, headers=headers)
            if response.status_code == 429 and attempt < 3:
                import time
                llm_logger.warning(f"Rate limit en chat/LLM (429), intento {attempt+1}. Esperando 30s...")
                await asyncio.sleep(30)
                continue
            elif response.status_code != 200:
                raise RuntimeError(f"Gemini API Error {response.status_code}: {response.text}")
            break
        
        res_data = response.json()
        usage = res_data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        
        try:
            text = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
            return text, prompt_tokens, completion_tokens
        except (KeyError, IndexError) as e:
            raise ValueError(f"Respuesta inesperada de Gemini API: {res_data}")

    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Envía un listado completo de mensajes al modelo de lenguaje."""
        anonymized_messages = []
        mapping = {}
        anonymizer = None

        if settings.ANONYMIZE_LLM_CALLS:
            try:
                from app.utils.anonymizer import DataAnonymizer
                from app.domain.schemas import AnonymizationSession
                anonymizer = DataAnonymizer()
                sess = AnonymizationSession()
                for msg in messages:
                    role = msg.get("role")
                    content = msg.get("content", "") or ""
                    anon_content, msg_map = anonymizer.anonymize(content, session=sess)
                    mapping.update(msg_map)
                    anonymized_messages.append({"role": role, "content": anon_content})
                try:
                    from app.api.routes import record_privacy_session
                    record_privacy_session({
                        "status": "protected",
                        "session_id": sess.session_id,
                        "total_protected_entities": len(sess.entities),
                        "entities_by_type": dict(sess.entity_counters),
                    })
                except Exception:
                    pass
            except Exception as e:
                from app.domain.exceptions import AnonymizationFailureError
                import uuid
                incident_id = str(uuid.uuid4())
                error_logger.error("Fallo crítico en anonimización (Fail-Closed activado): %s [Incidente: %s]", e, incident_id)
                raise AnonymizationFailureError(incident_id=incident_id, message=f"Fallo en la anonimización de datos pre-Gemini: {e}")
        else:
            anonymized_messages = messages

        import time
        start_time = time.perf_counter()
        p_tok, c_tok = 0, 0
        model_name = settings.GEMINI_MODEL_NAME

        # Si hay GEMINI_API_KEY o GEMINI_PROXY_URL configurada, usar Gemini
        if settings.GEMINI_PROXY_URL:
            llm_logger.info("Utilizando la API de Gemini para chat (en la nube)")
            temp = kwargs.get("options", {}).get("temperature", 0.7)
            content, p_tok, c_tok = await self._call_gemini_api(anonymized_messages, temperature=temp)
            model_name = settings.GEMINI_MODEL_NAME
        else:
            raise RuntimeError("GEMINI_PROXY_URL no está configurado. La conexión a Ollama ha sido descontinuada.")

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # Log metrics
        try:
            from app.infrastructure.monitoring.metrics_service import MetricsService
            from app.adapters.memory.memory import tenant_context
            cid = tenant_context.get()
            MetricsService.log_llm_metrics(
                client_id=cid,
                model_name=model_name,
                prompt_tokens=p_tok,
                completion_tokens=c_tok,
                latency_ms=latency_ms
            )
        except Exception as ex:
            llm_logger.warning("Error al registrar métricas de LLM en chat: %s", ex)

        if anonymizer:
            content = anonymizer.detokenize(content, mapping)

        return content




    async def stream_chat(self, messages: list[dict[str, str]], **kwargs):
        """Envía un listado completo de mensajes al modelo de lenguaje y devuelve un generador asíncrono (SSE)."""
        session = None
        mapping = {}
        anonymized_messages = []
        buffer = None

        if settings.ANONYMIZE_LLM_CALLS:
            from app.utils.anonymizer import DataAnonymizer
            from app.domain.schemas import AnonymizationSession
            from app.utils.streaming_buffer import StreamingTokenBuffer
            anonymizer = DataAnonymizer()
            session = AnonymizationSession()
            for msg in messages:
                content = msg.get("content", "") or ""
                anon_content, msg_map = anonymizer.anonymize(content, session=session)
                mapping.update(msg_map)
                anonymized_messages.append({"role": msg.get("role"), "content": anon_content})
            buffer = StreamingTokenBuffer()
            try:
                from app.api.routes import record_privacy_session
                record_privacy_session({
                    "status": "protected",
                    "session_id": session.session_id,
                    "total_protected_entities": len(session.entities),
                    "entities_by_type": dict(session.entity_counters),
                })
            except Exception:
                pass
        else:
            anonymized_messages = messages

        model_name = settings.GEMINI_MODEL_NAME

        if settings.GEMINI_PROXY_URL:
            url = settings.GEMINI_PROXY_URL
            headers = {"X-Alfonso-License-Token": settings.ALFONSO_CLIENT_SECRET}
            contents = []
            for msg in anonymized_messages:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
                
            payload = {
                "contents": contents,
                "model": model_name,
                "apiVersion": settings.GEMINI_API_VERSION,
                "stream": True
            }
            
            import httpx
            try:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code != 200:
                        yield f"Error: {response.status_code}"
                        return
                    async for chunk in response.aiter_text():
                        if chunk:
                            if buffer:
                                resolved = buffer.feed(chunk, mapping)
                                if resolved:
                                    yield resolved
                            else:
                                yield chunk
                    if buffer:
                        remaining = buffer.flush(mapping)
                        if remaining:
                            yield remaining
            finally:
                if session:
                    session.purge()
        else:
            raise RuntimeError("GEMINI_PROXY_URL no está configurado para streaming. La conexión a Ollama ha sido descontinuada.")

    async def generate(
        self,
        message: str,
        mode: str = "chat",
        request_id: str = None,
        memory: str | None = None,
        options: dict | None = None,
        _retry: int = 0,
        client_id: str | None = None,
    ) -> str:

        logger = attach_request_id(llm_logger, request_id)
        error = attach_request_id(error_logger, request_id)

        # Guardar valores originales para reintentos
        orig_message = message
        orig_memory = memory

        anonymizer = None
        mapping = {}
        if settings.ANONYMIZE_LLM_CALLS:
            from app.utils.anonymizer import DataAnonymizer
            anonymizer = DataAnonymizer()
            message, map1 = anonymizer.anonymize(message)
            mapping.update(map1)
            if memory:
                memory, map2 = anonymizer.anonymize(memory)
                mapping.update(map2)

        system_prompt = get_system_prompt(mode, client_id=client_id)

        if settings.GEMINI_PROXY_URL:
            if mode == "tool":
                from app.domain.prompt_generator import generate_tool_prompt
                tool_template = generate_tool_prompt(client_id)
                system_prompt = system_prompt + "\n\n" + tool_template

        messages = [{"role": "system", "content": system_prompt}]

        if memory:
            messages.append({"role": "system", "content": memory})

        messages.append({"role": "user", "content": message})

        num_ctx = settings.LLM_NUM_CTX_TOOL if mode == "tool" else settings.LLM_NUM_CTX_CHAT

        options_payload = {
            "num_ctx": num_ctx,
            "temperature": 0.0 if mode == "tool" else 0.7,
        }
        if options:
            options_payload.update(options)

        payload = {
            "model": settings.GEMINI_MODEL_NAME,
            "messages": messages,
            "stream": False,
            "keep_alive": -1,
            "options": options_payload,
        }

        if mode == "tool":
            try:
                from app.infrastructure.adapters.tool_registry import get_tool_schemas
                tool_schemas = get_tool_schemas()
                if tool_schemas:
                    payload["tools"] = tool_schemas
            except Exception as e:
                logger.warning("No se pudieron cargar los esquemas de herramientas para Gemini: %s", e)

        logger.info("MODEL=%s MODE=%s", settings.GEMINI_MODEL_NAME, mode)

        import time
        start_time = time.perf_counter()
        p_tok, c_tok = 0, 0
        model_name = settings.GEMINI_MODEL_NAME

        try:
            if not (settings.GEMINI_PROXY_URL):
                raise RuntimeError("GEMINI_PROXY_URL no está configurado.")
                
            logger.info("Utilizando la API de Gemini para generar (en la nube)")
            content, p_tok, c_tok = await self._call_gemini_api(messages, temperature=options_payload["temperature"])
            model_name = settings.GEMINI_MODEL_NAME

            if not content:
                raise ValueError("Empty response")

            # Extract and log think block if present (CoT in Chat)
            think_match = re.search(r"<think>(.*?)</think>", content, re.DOTALL | re.IGNORECASE)
            if think_match:
                thinking_text = think_match.group(1).strip()
                logger.info("DeepSeek-R1 Thought (CoT - Chat): %s", thinking_text)
                # Strip think block from final user-facing text
                content = _THINK_BLOCK.sub("", content).strip()

            if anonymizer:
                content = anonymizer.detokenize(content, mapping)

            # Log metrics
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            try:
                from app.infrastructure.monitoring.metrics_service import MetricsService
                from app.adapters.memory.memory import tenant_context
                cid = tenant_context.get()
                MetricsService.log_llm_metrics(
                    client_id=cid,
                    model_name=model_name,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                    latency_ms=latency_ms,
                    request_id=request_id
                )
            except Exception as ex:
                logger.warning("Error al registrar métricas de LLM en generate (fin): %s", ex)

            return content

        except Exception as e:

            if _retry < 2:
                await asyncio.sleep(2 ** _retry)
                return await self.generate(
                    orig_message,
                    mode=mode,
                    request_id=request_id,
                    memory=orig_memory,
                    options=options,
                    _retry=_retry + 1,
                    client_id=client_id,
                )

            error.exception("LLM failed permanently")

            if mode == "chat":
                return "Estoy teniendo problemas técnicos para responderte. Por favor, inténtalo de nuevo en unos instantes."

            return json.dumps({
                "tool": "no_op",
                "args": {"message": f"LLM_ERROR: {repr(e)}"}
            })

LLMClient = GeminiClient

