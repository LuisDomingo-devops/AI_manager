"""
SYSTEM TOOLS — Herramientas auxiliares del sistema operativo y control interactivo.

¿QUÉ HACE?
Proporciona utilidades para controlar periféricos de entrada (mouse/teclado), realizar capturas y OCR de pantalla, 
ejecutar comandos del sistema operativo y abrir/cerrar aplicaciones de forma local o remota a través del agente.
"""

import os
import platform
import shlex
import shutil
import subprocess
import psutil
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Sequence, Optional

from app.domain.actions import Action
from app.adapters.alfonso_bridge import bridge as alfonso_bridge
from app.utils.logger import tool_logger, error_logger

# ---------------------------------------------------------------------------
# Alias y detección de entorno
# ---------------------------------------------------------------------------

_IS_WSL = "microsoft" in platform.uname().release.lower() or \
          os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")

_APP_ALIASES: dict[str, list[str]] = {
    "internet":               ["xdg-open", "https://www.google.com"],
    "google":                 ["xdg-open", "https://www.google.com"],
    "explorador":             [],   # se resuelve con _find_file_manager
    "explorador de archivos": [],
    "gestor de archivos":     [],
    "file manager":           [],
    # Alias para nombres frecuentes en voz
    "chrome":                 ["google-chrome", "chromium-browser", "chromium"],
    "chromium":               ["chromium-browser", "chromium", "google-chrome"],
    "vscode":                 ["code"],
    "visual studio code":     ["code"],
    "terminal":               ["x-terminal-emulator", "gnome-terminal", "konsole", "xterm", "terminal", "bash", "sh", "cmd", "powershell"],
    "notepad":                ["gedit", "kate", "mousepad", "xed", "leafpad", "notepad"],
}

_FILE_MANAGERS = ["nautilus", "nemo", "thunar", "dolphin", "caja", "pcmanfm", "xdg-open"]

_DANGEROUS = {"rm", "del", "shutdown", "reboot", "poweroff", "format", "mkfs", "dd", ":()"}


def _find_file_manager() -> list[str] | None:
    for fm in _FILE_MANAGERS:
        if shutil.which(fm):
            tool_logger.info("Gestor de archivos detectado: %s", fm)
            if fm == "xdg-open":
                return [fm, str(Path.home())]
            return [fm]
    return None


def _has_display() -> bool:
    """Comprueba si hay un servidor X disponible."""
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _wsl_open(app_name: str) -> list[str] | None:
    """
    En WSL, intenta abrir una app Windows mediante PowerShell.
    Útil para firefox.exe, explorer.exe, etc.
    """
    if not _IS_WSL:
        return None
    # Intentar con powershell.exe Start-Process
    return ["powershell.exe", "-Command", f"Start-Process '{app_name}'"]


def _resolve_app(name: str) -> list[str] | None:
    """
    Resuelve el nombre de una aplicación a una lista de argumentos ejecutables.
    Devuelve None si no se puede resolver.
    """
    lower = name.strip().lower()

    # 1. Alias explícitos
    if lower in _APP_ALIASES:
        candidates = _APP_ALIASES[lower]
        if not candidates:
            return _find_file_manager()
        # Buscar el primero disponible
        for candidate in candidates:
            if shutil.which(candidate):
                return [candidate]
        return None

    # 2. Explorador de archivos por keywords
    if any(k in lower for k in ("explorad", "file manager", "gestor de archivo")):
        if _IS_WSL:
            return ["explorer.exe"]
        return _find_file_manager()

    # 3. Binario disponible directamente
    if shutil.which(name):
        return [name]

    # 4. En WSL: intentar via PowerShell
    if _IS_WSL:
        # Nombres comunes que pueden existir en Windows
        windows_apps = {
            "firefox": "firefox.exe",
            "chrome": "chrome.exe",
            "notepad": "notepad.exe",
            "explorer": "explorer.exe",
        }
        win_app = windows_apps.get(lower)
        if win_app:
            return [win_app]

    return None


def _normalize_command(command: str | Sequence[str]) -> list[str]:
    if isinstance(command, (list, tuple)):
        return list(command)

    command = command.strip()
    resolved = _resolve_app(command)
    if resolved:
        return resolved

    # Parsear como línea de comando normal
    try:
        if os.name == "nt":
            return shlex.split(command, posix=False)
        return shlex.split(command)
    except ValueError:
        return [command]


def _is_safe(command_parts: list[str]) -> bool:
    for token in command_parts:
        if token.lower() in _DANGEROUS:
            return False
    return True


# ---------------------------------------------------------------------------
# Tools - Sistema e Información
# ---------------------------------------------------------------------------

async def get_system_info() -> dict:
    tool_logger.info("Obteniendo información del sistema")
    try:
        return {
            "status": "ok",
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "is_wsl": _IS_WSL,
            "cpu_count": os.cpu_count(),
            "ram_total_gb": round(psutil.virtual_memory().total / 1024**3, 2),
            "ram_available_gb": round(psutil.virtual_memory().available / 1024**3, 2),
            "ram_used_percent": psutil.virtual_memory().percent,
            "disk_total_gb": round(psutil.disk_usage("/").total / 1024**3, 2),
            "disk_free_gb": round(psutil.disk_usage("/").free / 1024**3, 2),
        }
    except Exception as exc:
        error_logger.exception("Error obteniendo info del sistema")
        return {"status": "error", "message": str(exc)}


async def get_current_datetime() -> dict:
    tool_logger.info("Obteniendo fecha y hora del sistema")
    now = datetime.now()
    days_es = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    months_es = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return {
        "status": "ok",
        "iso": now.isoformat(),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": days_es[now.weekday()],
        "day": now.day,
        "month": months_es[now.month - 1],
        "year": now.year,
        "human": (
            f"{days_es[now.weekday()]}, {now.day} de {months_es[now.month - 1]}"
            f" de {now.year}, {now.strftime('%H:%M')}"
        ),
    }


async def open_application(command: str | Sequence[str], args: Sequence[str] | None = None, client_id: str | None = None) -> dict:
    command_parts = _normalize_command(command)
    if args:
        command_parts.extend(args)
    
    if not _is_safe(command_parts):
        error_logger.warning(f"Intento de ejecutar comando bloqueado por seguridad: {command_parts}")
        return {
            "status": "error",
            "message": "Operación de seguridad bloqueada: Este comando no está permitido."
        }

    command_text = " ".join(shlex.quote(str(part)) for part in command_parts)

    if alfonso_bridge.has_clients():
        tool_logger.info("Delegando open_application al agente local: %s", command_text)
        response = await alfonso_bridge.send_command(Action.OPEN_APP, {"command": command_text}, client_id=client_id)
        if response.get("status") == "success":
            return {
                "status": "ok",
                "message": response.get("result"),
                "delegate": "alfonso_agent",
                "command": command_text,
            }
        return {
            "status": "error",
            "message": response.get("error", "Error delegando al agente local."),
            "delegate": "alfonso_agent",
            "details": response,
        }

    return {
        "status": "error",
        "message": (
            f"No hay agente local conectado. No puedo abrir '{command_text}' en tu "
            "equipo. Arranca ui/alfonso_agent.py en tu máquina (Windows/Linux) y "
            "vuelve a intentarlo."
        ),
    }


async def close_application(command: str, client_id: str | None = None) -> dict:
    target = command.strip()
    
    command_parts = _normalize_command(target)
    if not _is_safe(command_parts):
        error_logger.warning(f"Intento de cerrar aplicación bloqueado por seguridad: {command_parts}")
        return {
            "status": "error",
            "message": "Operación de seguridad bloqueada: Este comando no está permitido."
        }

    if alfonso_bridge.has_clients():
        tool_logger.info("Delegando close_application al agente local: %s", target)
        response = await alfonso_bridge.send_command(Action.CLOSE_APP, {"command": target}, client_id=client_id)
        if response.get("status") == "success":
            return {
                "status": "ok",
                "message": response.get("result"),
                "delegate": "alfonso_agent",
                "command": target,
            }
        return {
            "status": "error",
            "message": response.get("error", "Error delegando al agente local."),
            "delegate": "alfonso_agent",
            "details": response,
        }

    error_logger.warning(
        "No hay agente local conectado (alfonso_bridge.has_clients()=False). "
        "No se puede cerrar '%s' en el equipo del usuario.",
        target,
    )

    return {
        "status": "error",
        "message": (
            f"No hay agente local conectado. No puedo cerrar '{target}' en tu "
            "equipo. Arranca ui/alfonso_agent.py en tu máquina y vuelve a intentarlo."
        ),
    }


async def open_url(url: str, client_id: str | None = None) -> dict:
    url = url.strip()
    if not url:
        return {"status": "error", "message": "URL no especificada"}

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if alfonso_bridge.has_clients():
        tool_logger.info("Delegando open_url al agente local: %s", url)
        response = await alfonso_bridge.send_command(Action.OPEN_URL, {"url": url}, client_id=client_id)
        if response.get("status") == "success":
            return {
                "status": "ok",
                "message": response.get("result"),
                "delegate": "alfonso_agent",
                "url": url,
            }
        return {
            "status": "error",
            "message": response.get("error", "Error abriendo la URL en el cliente."),
            "delegate": "alfonso_agent",
        }

    tool_logger.warning(
        "No hay agente local conectado; '%s' se abrirá en Playwright en el "
        "servidor y NO se verá en pantalla del cliente. Arranca "
        "ui/alfonso_agent.py para delegar correctamente.",
        url,
    )
    from app.tools.client.browser_tools import browser_navigate
    return await browser_navigate(url, client_id=client_id)


# ---------------------------------------------------------------------------
# Registro Unificado de Herramientas (TOOLS)
# ---------------------------------------------------------------------------

TOOLS = {
    # system_info / apps / url / date
    "system_info":          get_system_info,
    "open_application":     open_application,
    "close_application":    close_application,
    "get_current_datetime": get_current_datetime,
    "open_url":             open_url,
}
