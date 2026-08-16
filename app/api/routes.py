"""
ROUTES — Endpoints HTTP del API de Alfonso.

¿QUÉ HACE?
Centraliza y expone todos los endpoints del sistema (mensajería chat, navegación de navegador, uso de computadora, calendario nativo, cliente de correo electrónico y sandbox de desarrollo).

¿CUÁNDO LO HACE?
Cuando el servidor FastAPI arranca y se inicializa la aplicación. Maneja cada petición entrante HTTP del cliente.

¿CÓMO LO HACE?
Define un router principal y routers especializados (browser, computer, calendar, mail, dev), asociándolos a sus respectivos esquemas Pydantic y delegando la lógica de negocio a los agentes de core, herramientas y bases de datos.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/main.py: Registra el router raíz.
- app/domain/planner_orchestrator.py: Procesa las consultas en el endpoint /chat.
- app/domain/agents/marcos/marcos_agent.py: Asiste indirectamente en la generación de borradores inteligentes de correo.
- app/adapters/calendar_db.py y app/adapters/mail_db.py: Interactúan con las bases de datos de calendario y correo.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path
from typing import Any, List, Optional
from app.adapters.memory.memory import DB_PATH

import secrets
from fastapi import APIRouter, HTTPException, Query, Request, Depends, status, Form, File, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

# Imports del núcleo
from app.adapters import mail_db
from app.adapters.calendar_db import create_event, delete_event, list_events
from app.adapters.metrics import snapshot
from app.adapters.tool_registry import get_tool, list_tools
from app.utils.logger import app_logger, attach_request_id
from app.utils.timer import Timer
from app.config import settings

# ── API Key Security ────────────────────────────────────────────────────────
API_KEY_NAME = "X-API-Key"
SESSION_TOKEN_NAME = "X-Session-Token"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
session_token_header = APIKeyHeader(name=SESSION_TOKEN_NAME, auto_error=False)

async def verify_api_key(
    api_key: str = Depends(api_key_header),
    session_token: str = Depends(session_token_header)
):
    # 1. Comprobar si hay un token de sesión dinámico y es válido
    if session_token and isinstance(session_token, str):
        from app.infrastructure.security.session_manager import SessionManager
        client_id = SessionManager.validate_session_token(session_token)
        if client_id:
            return client_id

    # 2. Fallback a la API Key estática (admite inicialización de sesión)
    if api_key and isinstance(api_key, str) and secrets.compare_digest(api_key, settings.ALFONSO_API_KEY):
        from app.adapters.memory.memory import tenant_context
        # Si no se ha seteado contexto del tenant, dejar default
        if tenant_context.get() == "default":
            tenant_context.set("default")
        return "default"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Session Token or API Key"
    )

# ── Routers ─────────────────────────────────────────────────────────────────
router = APIRouter(prefix="")
router_browser = APIRouter(prefix="/browser", tags=["browser"], dependencies=[Depends(verify_api_key)])
router_computer = APIRouter(prefix="/computer", tags=["computer"], dependencies=[Depends(verify_api_key)])
router_calendar = APIRouter(prefix="/calendar", tags=["calendar"], dependencies=[Depends(verify_api_key)])
router_mail = APIRouter(prefix="/mail", tags=["mail"], dependencies=[Depends(verify_api_key)])
router_security = APIRouter(prefix="/security", tags=["security"], dependencies=[Depends(verify_api_key)])

# Inyectado desde lifespan en main.py
orchestrator: Any = None


# ---------------------------------------------------------------------------
# Schemas: Core
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    client_info: Optional[dict] = None


class LoginRequest(BaseModel):
    client_id: str


# ── Router de Autenticación de Sesiones ──────────────────────────────────────
router_auth = APIRouter(prefix="/auth", tags=["auth"])

@router_auth.post("/login")
async def login(payload: LoginRequest, api_key: str = Depends(api_key_header)):
    if not api_key or not secrets.compare_digest(api_key, settings.ALFONSO_API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API Key")
        
    from app.infrastructure.security.session_manager import SessionManager
    token = SessionManager.create_session(client_id=payload.client_id)
    return {"status": "ok", "session_token": token, "client_id": payload.client_id}

@router_auth.post("/logout")
async def logout(session_token: str = Depends(session_token_header)):
    if not session_token:
        raise HTTPException(status_code=400, detail="Session token header missing")
    from app.infrastructure.security.session_manager import SessionManager
    success = SessionManager.revoke_session_token(session_token)
    if not success:
        raise HTTPException(status_code=400, detail="Invalid or already revoked session token")
    return {"status": "ok", "message": "Sesión cerrada correctamente."}


# ---------------------------------------------------------------------------
# Schemas: Calendar
# ---------------------------------------------------------------------------

class EventCreate(BaseModel):
    title: str
    start_time: str
    end_time: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    attendees: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas: Dev Sandbox
# ---------------------------------------------------------------------------

class FilePayload(BaseModel):
    filename: str
    content: str


class CommandPayload(BaseModel):
    command: str


# ---------------------------------------------------------------------------
# Schemas: Browser & Computer Use
# ---------------------------------------------------------------------------

class BrowserNavigateRequest(BaseModel):
    url: str
    wait_until: str = "domcontentloaded"


class BrowserSearchRequest(BaseModel):
    query: str
    max_text_chars: int = Field(default=3000, ge=100, le=10000)


class BrowserClickRequest(BaseModel):
    selector: str
    button: str = "left"
    click_count: int = Field(default=1, ge=1, le=3)


class BrowserFillRequest(BaseModel):
    selector: str
    value: str


class BrowserScrollRequest(BaseModel):
    x: int = 0
    y: int = Field(default=500)
    selector: Optional[str] = None


class BrowserEvaluateRequest(BaseModel):
    script: str


class BrowserScreenshotRequest(BaseModel):
    full_page: bool = False
    save_path: Optional[str] = None


class ComputerMouseMoveRequest(BaseModel):
    x: int
    y: int
    duration: float = Field(default=0.25, ge=0.0, le=5.0)


class ComputerMouseClickRequest(BaseModel):
    x: int
    y: int
    button: str = "left"
    clicks: int = Field(default=1, ge=1, le=3)


class ComputerMouseDragRequest(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int
    duration: float = Field(default=0.5, ge=0.0, le=5.0)
    button: str = "left"


class ComputerKeyboardTypeRequest(BaseModel):
    text: str
    interval: float = Field(default=0.03, ge=0.0, le=1.0)


class ComputerKeyboardHotkeyRequest(BaseModel):
    keys: list[str] = Field(description="Lista de teclas, e.g. ['ctrl', 'c']")


class ComputerOCRScreenshotRequest(BaseModel):
    region: Optional[list[int]] = Field(
        default=None,
        description="[x, y, width, height] o null para pantalla completa"
    )
    lang: str = "spa+eng"


class ComputerOCRImageRequest(BaseModel):
    path: str
    lang: str = "spa+eng"


class ComputerFindOnScreenRequest(BaseModel):
    template_path: str
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    region: Optional[list[int]] = None


class ComputerWindowFocusRequest(BaseModel):
    title: str


class ComputerWindowCloseRequest(BaseModel):
    title: str


class ComputerScreenshotRequest(BaseModel):
    region: Optional[list[int]] = None
    save_path: Optional[str] = None


# ---------------------------------------------------------------------------
# Schemas: Mail
# ---------------------------------------------------------------------------

class EmailResponse(BaseModel):
    id: int
    sender: str
    recipient: str
    subject: str
    body: str
    received_at: str
    category: Optional[str]
    importance: str
    read_status: int
    summary: Optional[str]


class SendEmailRequest(BaseModel):
    recipient: str
    subject: str
    body: str


class ReplyEmailRequest(BaseModel):
    body: str
    reply_all: Optional[bool] = False


class ForwardEmailRequest(BaseModel):
    recipient: str
    comment: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers: Browser/Computer Use
# ---------------------------------------------------------------------------

def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or str(uuid.uuid4())


def _tool_response(request_id: str, result: dict, t: Timer) -> dict:
    status = "success" if result.get("status") == "ok" else "error"
    logger = attach_request_id(app_logger, request_id)
    logger.info("RESPUESTA TOOL DIRECTO: %s", result)
    return {
        "status": status,
        "request_id": request_id,
        "result": result,
        "latency_seconds": t.elapsed,
    }


async def _call_tool(tool_name: str, request_id: str, **kwargs) -> dict:
    tool = get_tool(tool_name, request_id=request_id)
    if not tool:
        return {"status": "error", "message": f"Tool no disponible: {tool_name}"}
    return await tool(**kwargs)


# ---------------------------------------------------------------------------
# Endpoints: Core
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok", "phase": "3"}


@router.get("/tools", dependencies=[Depends(verify_api_key)])
async def tools_list():
    return {"tools": list_tools()}


@router.get("/agents", dependencies=[Depends(verify_api_key)])
async def agents_list():
    return {
        "agents": [],
        "note": "Capa de agentes/EventBus retirada en Fase 4; PlannerOrchestrator es el único pipeline."
    }


@router.get("/metrics", dependencies=[Depends(verify_api_key)])
async def metrics():
    return snapshot()


@router.post("/chat", dependencies=[Depends(verify_api_key)])
async def chat_endpoint(req: ChatRequest, request: Request):
    from app.main import llm

    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    logger = attach_request_id(app_logger, request_id)

    session_id = request.headers.get("X-Session-ID") or req.session_id or request_id

    client_id = None
    if req.client_info:
        from app.adapters.alfonso_bridge import bridge
        if bridge.client_info:
            bridge.client_info.update(req.client_info)
        else:
            bridge.client_info = req.client_info
        client_id = req.client_info.get("client_id")

    logger.info("Solicitud /chat recibida")
    logger.info("SESSION_ID: %s", session_id)
    logger.info("CLIENT_ID: %s", client_id)
    logger.info("USER MESSAGE: %s", req.message)

    with Timer() as t:
        result = await orchestrator.run(
            req.message,
            llm,
            request_id=request_id,
            session_id=session_id,
            client_id=client_id,
        )

    status = result.get("type", "unknown")
    logger.info("Solicitud /chat procesada con estado: %s", status)
    if status == "chat":
        logger.info("RESPUESTA ENVIADA AL USUARIO (CHAT): %s", result.get("response"))
    elif status == "tool":
        logger.info("RESPUESTA ENVIADA AL USUARIO (TOOL %s): %s", result.get("tool"), result.get("result"))
    elif status == "multi_tool":
        logger.info("RESPUESTA ENVIADA AL USUARIO (MULTI_TOOL): %s", result.get("results"))
    else:
        logger.info("RESPUESTA ENVIADA AL USUARIO: %s", result)
    logger.info("LATENCY: %.2fs", t.elapsed)

    return {"request_id": request_id, "result": result}


class MetadataPatch(BaseModel):
    title: Optional[str] = None
    discipline: Optional[str] = None
    project_name: Optional[str] = None
    is_persistent: Optional[bool] = None

@router.get("/conversations", dependencies=[Depends(verify_api_key)])
async def get_conversations():
    from app.adapters.memory.memory import memory
    convs = memory.list_persistent_conversations()
    return {"conversations": convs, "count": len(convs)}


@router.patch("/conversations/{session_id}", dependencies=[Depends(verify_api_key)])
async def patch_conversation(session_id: str, payload: MetadataPatch):
    from app.adapters.memory.memory import memory
    existing = memory.get_metadata(session_id)
    if not existing:
        # Si no existe metadato aún, creamos uno base
        title = payload.title or "Nueva conversación"
        discipline = payload.discipline or "general"
        project_name = payload.project_name or "default"
        is_persistent = payload.is_persistent if payload.is_persistent is not None else True
    else:
        title = payload.title if payload.title is not None else existing["title"]
        discipline = payload.discipline if payload.discipline is not None else existing["discipline"]
        project_name = payload.project_name if payload.project_name is not None else existing["project_name"]
        is_persistent = payload.is_persistent if payload.is_persistent is not None else existing["is_persistent"]

    memory.upsert_metadata(session_id, title, discipline, project_name, is_persistent)
    return {"status": "ok", "session_id": session_id}


@router.get("/memory/{session_id}", dependencies=[Depends(verify_api_key)])
async def get_memory(session_id: str):
    from app.adapters.memory.memory import memory
    history = memory.get_history(session_id)
    metadata = memory.get_metadata(session_id)
    return {
        "session_id": session_id,
        "metadata": metadata,
        "messages": history,
        "count": len(history)
    }


@router.delete("/memory/{session_id}", dependencies=[Depends(verify_api_key)])
async def clear_memory(session_id: str):
    from app.adapters.memory.memory import memory
    memory.clear(session_id)
    # También limpiar metadatos al borrar memoria
    with sqlite3.connect(str(DB_PATH), check_same_thread=False) as conn:
        conn.execute("DELETE FROM conversation_metadata WHERE session_id = ?", (session_id,))
        conn.commit()
    return {"status": "ok", "session_id": session_id, "message": "Historial borrado"}


@router.get("/memory", dependencies=[Depends(verify_api_key)])
async def list_sessions():
    from app.adapters.memory.memory import memory
    sessions = memory.list_sessions()
    return {"sessions": sessions, "count": len(sessions)}


# ---------------------------------------------------------------------------
# Endpoints: Calendar
# ---------------------------------------------------------------------------

@router_calendar.get("/events")
async def get_events(
    start_date: Optional[str] = Query(None, description="Fecha de inicio (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Fecha de fin (YYYY-MM-DD)"),
):
    try:
        events = list_events(start_date=start_date, end_date=end_date)
        return {"status": "ok", "events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo eventos: {str(e)}")


@router_calendar.post("/events")
async def post_event(event: EventCreate):
    try:
        event_id = create_event(
            title=event.title,
            start_time=event.start_time,
            end_time=event.end_time,
            description=event.description,
            location=event.location,
            attendees=event.attendees,
        )
        
        fact = f"Cita agendada: '{event.title}' el {event.start_time}"
        if event.location:
            fact += f" en {event.location}"
        if event.attendees:
            fact += f" con {event.attendees}"
            
        from app.adapters.memory.vector_memory import vector_memory
        vector_memory.add_fact("global", fact)
        
        from app.adapters.alfonso_bridge import bridge
        if bridge.has_clients():
            await bridge.send_command("calendar.sync", {"action": "create", "id": event_id})
            
        return {"status": "ok", "event_id": event_id, "message": "Evento creado exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando evento: {str(e)}")


@router_calendar.delete("/events/{event_id}")
async def remove_event(event_id: int):
    try:
        success = delete_event(event_id)
        if not success:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
            
        from app.adapters.alfonso_bridge import bridge
        if bridge.has_clients():
            await bridge.send_command("calendar.sync", {"action": "delete", "id": event_id})
            
        return {"status": "ok", "message": f"Evento con ID {event_id} eliminado correctamente."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error eliminando evento: {str(e)}")


# ---------------------------------------------------------------------------
# Endpoints: Browser
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Endpoints: Browser
# ---------------------------------------------------------------------------

@router_browser.post("/navigate")
async def browser_navigate_endpoint(req: BrowserNavigateRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_navigate", rid, url=req.url, wait_until=req.wait_until)
    return _tool_response(rid, result, t)


@router_browser.post("/search")
async def browser_search_endpoint(req: BrowserSearchRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_search", rid, query=req.query, max_text_chars=req.max_text_chars)
    return _tool_response(rid, result, t)


@router_browser.post("/click")
async def browser_click_endpoint(req: BrowserClickRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool(
            "browser_click", rid,
            selector=req.selector,
            button=req.button,
            click_count=req.click_count,
        )
    return _tool_response(rid, result, t)


@router_browser.post("/fill")
async def browser_fill_endpoint(req: BrowserFillRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_fill", rid, selector=req.selector, value=req.value)
    return _tool_response(rid, result, t)


@router_browser.post("/submit")
async def browser_submit_endpoint(request: Request, selector: str):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_submit", rid, selector=selector)
    return _tool_response(rid, result, t)


@router_browser.post("/scroll")
async def browser_scroll_endpoint(req: BrowserScrollRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_scroll", rid, x=req.x, y=req.y, selector=req.selector)
    return _tool_response(rid, result, t)


@router_browser.post("/evaluate")
async def browser_evaluate_endpoint(req: BrowserEvaluateRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_evaluate", rid, script=req.script)
    return _tool_response(rid, result, t)


@router_browser.post("/screenshot")
async def browser_screenshot_endpoint(req: BrowserScreenshotRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool(
            "browser_screenshot", rid,
            full_page=req.full_page,
            save_path=req.save_path,
        )
    return _tool_response(rid, result, t)


@router_browser.get("/text")
async def browser_get_text_endpoint(request: Request, selector: str = "body"):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_get_text", rid, selector=selector)
    return _tool_response(rid, result, t)


@router_browser.delete("/close")
async def browser_close_endpoint(request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("browser_close", rid)
    return _tool_response(rid, result, t)


# ---------------------------------------------------------------------------
# Endpoints: Computer Use
# ---------------------------------------------------------------------------

@router_computer.post("/screenshot")
async def computer_screenshot_endpoint(req: ComputerScreenshotRequest, request: Request):
    rid = _request_id(request)
    region = tuple(req.region) if req.region and len(req.region) == 4 else None
    with Timer() as t:
        result = await _call_tool("screenshot", rid, region=region, save_path=req.save_path)
    return _tool_response(rid, result, t)


@router_computer.post("/mouse/move")
async def mouse_move_endpoint(req: ComputerMouseMoveRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("mouse_move", rid, x=req.x, y=req.y, duration=req.duration)
    return _tool_response(rid, result, t)


@router_computer.post("/mouse/click")
async def mouse_click_endpoint(req: ComputerMouseClickRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool(
            "mouse_click", rid,
            x=req.x, y=req.y,
            button=req.button,
            clicks=req.clicks,
        )
    return _tool_response(rid, result, t)


@router_computer.post("/mouse/drag")
async def mouse_drag_endpoint(req: ComputerMouseDragRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool(
            "mouse_drag", rid,
            x1=req.x1, y1=req.y1,
            x2=req.x2, y2=req.y2,
            duration=req.duration,
            button=req.button,
        )
    return _tool_response(rid, result, t)


@router_computer.post("/keyboard/type")
async def keyboard_type_endpoint(req: ComputerKeyboardTypeRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("keyboard_type", rid, text=req.text, interval=req.interval)
    return _tool_response(rid, result, t)


@router_computer.post("/keyboard/hotkey")
async def keyboard_hotkey_endpoint(req: ComputerKeyboardHotkeyRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        tool = get_tool("keyboard_hotkey", request_id=rid)
        if not tool:
            result = {"status": "error", "message": "Tool no disponible: keyboard_hotkey"}
        else:
            result = await tool(*req.keys)
    return _tool_response(rid, result, t)


@router_computer.post("/ocr/screenshot")
async def ocr_screenshot_endpoint(req: ComputerOCRScreenshotRequest, request: Request):
    rid = _request_id(request)
    region = tuple(req.region) if req.region and len(req.region) == 4 else None
    with Timer() as t:
        result = await _call_tool("ocr_screenshot", rid, region=region, lang=req.lang)
    return _tool_response(rid, result, t)


@router_computer.post("/ocr/image")
async def ocr_image_endpoint(req: ComputerOCRImageRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("ocr_image", rid, path=req.path, lang=req.lang)
    return _tool_response(rid, result, t)


@router_computer.post("/find")
async def find_on_screen_endpoint(req: ComputerFindOnScreenRequest, request: Request):
    rid = _request_id(request)
    region = tuple(req.region) if req.region and len(req.region) == 4 else None
    with Timer() as t:
        result = await _call_tool(
            "find_on_screen", rid,
            template_path=req.template_path,
            threshold=req.threshold,
            region=region,
        )
    return _tool_response(rid, result, t)


@router_computer.get("/windows")
async def window_list_endpoint(request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("window_list", rid)
    return _tool_response(rid, result, t)


@router_computer.post("/windows/focus")
async def window_focus_endpoint(req: ComputerWindowFocusRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("window_focus", rid, title=req.title)
    return _tool_response(rid, result, t)


@router_computer.post("/windows/close")
async def window_close_endpoint(req: ComputerWindowCloseRequest, request: Request):
    rid = _request_id(request)
    with Timer() as t:
        result = await _call_tool("window_close", rid, title=req.title)
    return _tool_response(rid, result, t)


# ---------------------------------------------------------------------------
# Endpoints: Mail
# ---------------------------------------------------------------------------

@router_mail.get("/emails", response_model=List[EmailResponse])
async def get_emails(
    category: Optional[str] = None,
    importance: Optional[str] = None,
    read_status: Optional[int] = None,
    limit: int = 50,
):
    """Obtiene la lista de correos con filtros opcionales."""
    try:
        import asyncio
        from app.tools.server.mail_tools import sync_emails_to_calendar
        asyncio.create_task(sync_emails_to_calendar())

        emails = mail_db.list_emails(
            category=category,
            importance=importance,
            read_status=read_status,
            limit=limit
        )
        return emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_mail.get("/emails/{email_id}", response_model=EmailResponse)
async def get_email_detail(email_id: int):
    """Obtiene el contenido completo de un correo por su ID."""
    email = mail_db.get_email(email_id)
    if not email:
        raise HTTPException(status_code=404, detail=f"No se encontró ningún correo con ID {email_id}.")
    return email


@router_mail.post("/emails/{email_id}/read")
async def mark_email_as_read(email_id: int):
    """Marca un correo electrónico como leído."""
    success = mail_db.update_email(email_id, read_status=1)
    if not success:
        email = mail_db.get_email(email_id)
        if not email:
            raise HTTPException(status_code=404, detail=f"No se encontró ningún correo con ID {email_id}.")
        return {"status": "ok", "message": "El correo ya estaba marcado como leído."}
    return {"status": "ok", "message": f"Correo con ID {email_id} marcado como leído."}


@router_mail.post("/emails/seed")
async def seed_emails():
    """Inyecta correos de prueba simulados en la base de datos."""
    try:
        inserted = mail_db.seed_mock_emails()
        import asyncio
        from app.tools.server.mail_tools import sync_emails_to_calendar
        asyncio.create_task(sync_emails_to_calendar())
        return {
            "status": "ok",
            "message": f"Inyección completada. Se han insertado {inserted} correos de prueba.",
            "inserted_count": inserted
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_mail.post("/send")
async def send_new_email(req: SendEmailRequest):
    """Envía un nuevo correo y lo guarda."""
    from app.tools.server.mail_tools import mail_send_email
    res = await mail_send_email(req.recipient, req.subject, req.body)
    if res["status"] == "error":
        raise HTTPException(status_code=500, detail=res["message"])
    return res


@router_mail.post("/drafts")
async def save_draft(payload: dict):
    """Guarda un borrador de correo."""
    subject = payload.get("subject", "")
    recipient = payload.get("recipient", "")
    body = payload.get("body", "")
    
    from app.adapters.mail_db import create_email
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    email_id = create_email(
        sender="luisd@alfonso.dev",
        recipient=recipient,
        subject=subject,
        body=body,
        received_at=now_str,
        category="draft",
        importance="Media",
        read_status=1,
        summary="Borrador guardado."
    )
    return {"status": "ok", "email_id": email_id}


@router_mail.delete("/emails/{email_id}")
async def delete_existing_email(email_id: int):
    """Elimina un correo por su ID."""
    from app.tools.server.mail_tools import mail_delete_email
    res = await mail_delete_email(email_id)
    if res["status"] == "error":
        raise HTTPException(status_code=404, detail=res["message"])
    return res


@router_mail.post("/emails/{email_id}/reply")
async def reply_existing_email(email_id: int, req: ReplyEmailRequest):
    """Envía una respuesta a un correo por su ID."""
    from app.tools.server.mail_tools import mail_reply_email
    res = await mail_reply_email(email_id, req.body, req.reply_all)
    if res["status"] == "error":
        raise HTTPException(status_code=500, detail=res["message"])
    return res


@router_mail.post("/emails/{email_id}/forward")
async def forward_existing_email(email_id: int, req: ForwardEmailRequest):
    """Reenvía un correo por su ID."""
    from app.tools.server.mail_tools import mail_forward_email
    res = await mail_forward_email(email_id, req.recipient, req.comment)
    if res["status"] == "error":
        raise HTTPException(status_code=500, detail=res["message"])
    return res


@router_mail.get("/emails/{email_id}/draft")
async def get_smart_reply_draft(email_id: int):
    """Genera un borrador de respuesta inteligente (asistente experto si es legal)."""
    from app.tools.server.mail_tools import mail_generate_draft
    res = await mail_generate_draft(email_id)
    if res["status"] == "error":
        raise HTTPException(status_code=500, detail=res["message"])
    return res


# ── Security Endpoints ──────────────────────────────────────────────────────

@router_security.get("/status")
async def get_security_status():
    from app.domain.agents.security.security_agent import security_agent
    return {
        "status": "success",
        "active_alerts_count": len([a for a in security_agent.alerts if a["level"] in ["WARNING", "HIGH"]]),
        "total_alerts_count": len(security_agent.alerts),
        "blocked_ips_count": len(security_agent.blocked_ips),
        "last_scan_time": security_agent.last_scan_time
    }

@router_security.get("/alerts")
async def get_security_alerts():
    from app.domain.agents.security.security_agent import security_agent
    return {
        "status": "success",
        "alerts": security_agent.alerts
    }

@router_security.post("/scan")
async def trigger_security_scan():
    from app.domain.agents.security.security_agent import security_agent
    await security_agent.scan_system()
    return {
        "status": "success",
        "message": "Manual security scan completed successfully.",
        "active_alerts_count": len([a for a in security_agent.alerts if a["level"] in ["WARNING", "HIGH"]]),
        "total_alerts_count": len(security_agent.alerts)
    }


# ── Tax Endpoints ──────────────────────────────────────────────────────────
router_tax = APIRouter(prefix="/tax", tags=["tax"], dependencies=[Depends(verify_api_key)])

@router_tax.get("/aggregates")
async def get_tax_aggregates(year: Optional[int] = None):
    try:
        from app.domain.services.tax_parser_service import TaxParserService
        aggregates = TaxParserService.get_quarterly_aggregates(year=year)
        return {"status": "ok", "aggregates": aggregates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_tax.get("/profile")
async def get_user_profile():
    try:
        from app.adapters.memory.memory import _get_connection
        from app.utils.encryption import encryptor
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_type, nif, razon_social, direccion, cert_path, cert_password FROM user_profile LIMIT 1")
            row = cursor.fetchone()
            
        if not row:
            return {"status": "ok", "configured": False, "profile": None}
            
        return {
            "status": "ok",
            "configured": True,
            "profile": {
                "user_type": row["user_type"],
                "nif": encryptor.decrypt(row["nif"]),
                "razon_social": encryptor.decrypt(row["razon_social"]),
                "direccion": encryptor.decrypt(row["direccion"]),
                "cert_path": encryptor.decrypt(row["cert_path"]),
                "cert_password_masked": "******" if row["cert_password"] else None
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_tax.post("/profile")
async def save_user_profile(
    user_type: str = Form(...),
    nif: str = Form(...),
    razon_social: str = Form(...),
    direccion: str = Form(...),
    cert_password: Optional[str] = Form(None),
    certificate: Optional[UploadFile] = File(None)
):
    try:
        from app.domain.schemas import UserProfileSchema
        from pydantic import ValidationError
        
        try:
            profile = UserProfileSchema(
                user_type=user_type,
                nif=nif,
                razon_social=razon_social,
                direccion=direccion,
                cert_password=cert_password
            )
            # Usar los campos normalizados/limpios por Pydantic
            user_type = profile.user_type
            nif = profile.nif
            razon_social = profile.razon_social
            direccion = profile.direccion
        except ValidationError as val_err:
            raise HTTPException(status_code=400, detail=str(val_err))

        from app.adapters.memory.memory import _get_connection
        from app.utils.encryption import encryptor
        import shutil
        from pathlib import Path
        
        cert_path_str = ""
        if certificate:
            cert_dir = Path("data/certificates")
            cert_dir.mkdir(parents=True, exist_ok=True)
            cert_file_path = cert_dir / certificate.filename
            with open(cert_file_path, "wb") as buffer:
                shutil.copyfileobj(certificate.file, buffer)
            cert_path_str = str(cert_file_path.resolve()).replace("\\", "/")

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_profile")
            cursor.execute("""
                INSERT INTO user_profile (user_type, nif, razon_social, direccion, cert_path, cert_password)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                user_type,
                encryptor.encrypt(nif),
                encryptor.encrypt(razon_social),
                encryptor.encrypt(direccion),
                encryptor.encrypt(cert_path_str) if cert_path_str else None,
                encryptor.encrypt(cert_password) if cert_password else None
            ))
            conn.commit()
            
        return {"status": "ok", "message": "Perfil fiscal y certificado guardados correctamente en el servidor."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_tax.post("/bank/import")
async def import_bank_statement_file(file: UploadFile = File(...), connection_id: Optional[int] = Query(None)):
    try:
        from app.domain.services.bank_service import BankService
        import tempfile
        import shutil
        import os
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp:
            shutil.copyfileobj(file.file, temp)
            temp_path = temp.name
            
        try:
            count = BankService.parse_norma43_file(temp_path, connection_id)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
        return {
            "status": "ok",
            "message": f"Extracto bancario procesado. Se importaron {count} movimientos.",
            "imported_count": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router_tax.get("/bank/mock-auth", response_class=HTMLResponse)
async def bank_mock_auth(redirect: str, bank: str = "BBVA"):
    from fastapi.responses import HTMLResponse
    html_content = f"""
    <html>
        <head>
            <title>Simulacion de Autorizacion Bancaria</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #0f172a;
                    color: #e2e8f0;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .card {{
                    background-color: #1e293b;
                    padding: 30px;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
                    text-align: center;
                    max-width: 400px;
                    border: 1px solid #334155;
                }}
                h1 {{
                    color: #38bdf8;
                    font-size: 24px;
                    margin-bottom: 20px;
                }}
                p {{
                    color: #94a3b8;
                    margin-bottom: 30px;
                    line-height: 1.5;
                }}
                .btn {{
                    background-color: #0284c7;
                    color: white;
                    padding: 12px 24px;
                    border: none;
                    border-radius: 6px;
                    font-weight: bold;
                    cursor: pointer;
                    text-decoration: none;
                    display: inline-block;
                    transition: background-color 0.2s;
                }}
                .btn:hover {{
                    background-color: #0369a1;
                }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Conectar Alfonso con {bank}</h1>
                <p>Estás en el portal seguro de autorización de <strong>{bank}</strong>. Al hacer clic en el botón de abajo, permitirás que Alfonso acceda a los movimientos de tu cuenta para la conciliación fiscal.</p>
                <a href="{redirect}" class="btn">Autorizar Acceso</a>
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@router_tax.get("/boe/check")
async def check_boe_endpoint(date: Optional[str] = Query(None, description="Fecha en formato YYYYMMDD")):
    try:
        from datetime import datetime
        from app.domain.services.boe_reader import BOEReaderService
        alerts = await BOEReaderService.fetch_and_parse_boe(date_str=date)
        suggested = await BOEReaderService.analyze_fiscal_alerts(alerts)
        return {
            "status": "ok",
            "date": date or datetime.now().strftime("%Y%m%d"),
            "alerts_found_count": len(alerts),
            "alerts": alerts,
            "suggested_updates": suggested
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Endpoint de la Declaración Responsable de Conformidad (Real Decreto 1007/2023)
@router.get("/compliance-declaration")
async def get_compliance_declaration():
    from app.config import settings
    return {
        "status": "ok",
        "compliance": {
            "developer": settings.SIF_DEVELOPER,
            "software_name": settings.SIF_SOFTWARE_NAME,
            "version": settings.SIF_VERSION,
            "regulation": settings.SIF_REGULATION,
            "certified_date": settings.SIF_CERTIFIED_DATE,
            "statement": (
                f"{settings.SIF_DEVELOPER} declara bajo su responsabilidad que el sistema informático de facturación "
                f"'{settings.SIF_SOFTWARE_NAME}' versión {settings.SIF_VERSION} cumple con todos los requisitos establecidos en el "
                "artículo 29.2.j) de la Ley 58/2003, de 17 de diciembre, General Tributaria, y en su reglamento "
                "de desarrollo aprobado por el Real Decreto 1007/2023, de 5 de diciembre, así como en las "
                "especificaciones técnicas de la Orden HAC/1177/2024. Garantizando la integridad, conservación, "
                "accesibilidad, legibilidad, trazabilidad e inalterabilidad de los registros de facturación sin "
                "interpolaciones, omisiones ni alteraciones de las que no quede la debida anotación en el sistema."
            ),
            "signature": f"FIRMADO DIGITALMENTE POR REPRESENTANTE LEGAL DE {settings.SIF_DEVELOPER.upper()}"
        }
    }


# Endpoint de Métricas de Consumo del LLM e Inferencia
@router.get("/monitoring/metrics")
async def get_monitoring_metrics(client_id: str = Depends(verify_api_key)):
    from app.infrastructure.monitoring.metrics_service import MetricsService
    from app.adapters.memory.memory import tenant_context
    cid = tenant_context.get()
    summary = MetricsService.get_llm_metrics_summary(client_id=cid)
    return {
        "status": "ok",
        "client_id": cid,
        "metrics": summary
    }


# Incluimos los sub-routers en el router principal
router.include_router(router_auth)
router.include_router(router_browser)
router.include_router(router_computer)
router.include_router(router_calendar)
router.include_router(router_mail)
router.include_router(router_security)
router.include_router(router_tax)


# ── WebSocket de Alfonso Guardián ───────────────────────────────────────────
from fastapi import WebSocket, WebSocketDisconnect
from app.core.websocket_manager import guardian_ws_manager

@router.websocket("/ws/guardian")
async def websocket_guardian_endpoint(websocket: WebSocket):
    await guardian_ws_manager.connect(websocket)
    try:
        while True:
            # Escucha mensajes de la extensión (ej. confirmación de firma, logs)
            data = await websocket.receive_json()
            app_logger.info(f"Mensaje recibido de la extensión Guardián: {data}")
            # Eco simple de confirmación
            await websocket.send_json({"status": "received", "echo": data})
    except WebSocketDisconnect:
        guardian_ws_manager.disconnect(websocket)
    except Exception as e:
        app_logger.error(f"Error en websocket_guardian_endpoint: {e}")
        guardian_ws_manager.disconnect(websocket)


