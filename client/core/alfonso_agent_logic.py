import subprocess
import pyautogui
import os
import base64
import logging
import asyncio
import shutil
import platform
from io import BytesIO
import webbrowser

# Importar el gestor de registro de apps
from core.app_registry import update_app_registry, load_app_registry, get_app_path, _KNOWN_APPS

logger = logging.getLogger(__name__)

# Desactivar el fail-safe de PyAutoGUI para evitar que se detenga si el ratón se mueve a una esquina
pyautogui.FAILSAFE = False

_IS_WINDOWS = platform.system() == "Windows"


class AlfonsoAgentLogic:
    """Encapsulates the logic for executing local system commands."""

    def __init__(self, registry_file=".env.apps"):
        self._system = platform.system()
        self.registry_file = registry_file
        self.app_registry = {}
        
        # Cargar registro de aplicaciones al inicializar
        self._load_registry()
    
    def _load_registry(self):
        """Carga y actualiza el registro de aplicaciones."""
        logger.info("Actualizando registro de aplicaciones instaladas...")
        try:
            update_app_registry(self.registry_file)
            self.app_registry = load_app_registry(self.registry_file)
            logger.info(f"✓ Registro cargado: {len(self.app_registry)} aplicaciones disponibles")
        except Exception as e:
            logger.warning(f"No se pudo actualizar registro de apps: {e}")
            self.app_registry = {}

    def _resolve_local_path(self, raw_path: str) -> str:
        if not raw_path:
            return raw_path
        
        # 1. Normalizar barras
        path = raw_path.replace("\\", "/")

        # Eliminar prefijos comunes como "mi ", "el ", "la "
        import re
        path = re.sub(r"\b(mi|el|la|los|las)\s+(escritorio|desktop|documentos|documents|descargas|downloads|imagenes|imágenes|pictures|musica|música|music|videos|perfil|usuario|home|inicio)\b", r"\2", path, flags=re.IGNORECASE)
        
        # 2. Si estamos en Windows, traducir rutas de WSL (/mnt/<drive>/...)
        if self._system == "Windows":
            # Traducir /mnt/c/... a C:\...
            mnt_match = re.match(r"^/mnt/([a-zA-Z])(.*)$", path)
            if mnt_match:
                drive = mnt_match.group(1).upper()
                remainder = mnt_match.group(2).replace("/", "\\")
                path = f"{drive}:{remainder}"
                logger.info(f"Ruta de WSL detectada en Windows. Corrigiendo a: {path}")
            
            # Traducir /home/<user>/... a \\wsl.localhost\Ubuntu\home\<user>\...
            home_match = re.match(r"^/home/([^/]+)(.*)$", path)
            if home_match:
                user = home_match.group(1)
                remainder = home_match.group(2).replace("/", "\\")
                path = f"\\\\wsl.localhost\\Ubuntu\\home\\{user}{remainder}"
                logger.info(f"Ruta de home de WSL detectada en Windows. Corrigiendo a UNC: {path}")

        # 3. Mapear rutas absolutas de macOS o de otros usuarios al home del usuario local
        match = re.match(r"^(?:/Users/[^/]+|C:/Users/[^/]+)(/.*)$", path, re.IGNORECASE)
        if match:
            remainder = match.group(1).lstrip("/")
            home = os.path.expanduser("~")
            path = os.path.join(home, remainder)

        # 4. Expandir ~ o ~/ a HOME del usuario local
        if path.startswith("~/"):
            home = os.path.expanduser("~")
            path = path.replace("~/", home + "/")
        elif path.startswith("~"):
            home = os.path.expanduser("~")
            path = home + path[1:]

        # 5. Redireccionar carpetas comunes (Escritorio, Documentos, Descargas, etc.) al HOME del usuario
        parts = path.split("/")
        if len(parts) >= 1:
            for idx, part in enumerate(parts):
                part_lower = part.lower()
                target_folder = None
                
                if part_lower in ["desktop", "escritorio"]:
                    target_folder = "Desktop"
                elif part_lower in ["documents", "documentos"]:
                    target_folder = "Documents"
                elif part_lower in ["downloads", "descargas"]:
                    target_folder = "Downloads"
                elif part_lower in ["pictures", "imagenes", "imágenes"]:
                    target_folder = "Pictures"
                elif part_lower in ["music", "musica", "música"]:
                    target_folder = "Music"
                elif part_lower in ["videos"]:
                    target_folder = "Videos"
                elif part_lower in ["perfil", "usuario", "home", "inicio"]:
                    remainder = "/".join(parts[idx+1:])
                    path = os.path.join(os.path.expanduser("~"), remainder)
                    break
                
                if target_folder:
                    home = os.path.expanduser("~")
                    resolved_dir = os.path.join(home, target_folder)
                    # Si no existe en inglés, buscar en español
                    if not os.path.exists(resolved_dir):
                        spanish_mappings = {
                            "Desktop": "Escritorio",
                            "Documents": "Documentos",
                            "Downloads": "Descargas",
                            "Pictures": "Imágenes",
                            "Music": "Música",
                        }
                        if target_folder in spanish_mappings:
                            alt_dir = os.path.join(home, spanish_mappings[target_folder])
                            if os.path.exists(alt_dir):
                                resolved_dir = alt_dir
                                
                    remainder = "/".join(parts[idx+1:])
                    path = os.path.join(resolved_dir, remainder)
                    break

        resolved_path = os.path.normpath(path)
        
        # 6. Si la ruta final resuelta no existe, buscar el nombre del archivo/carpeta en el perfil
        if not os.path.exists(resolved_path):
            basename = os.path.basename(resolved_path)
            # Solo buscar si es un nombre simple o relativo corto
            if basename and (basename == path or "/" not in path):
                # Simular _find_in_home si no está importado localmente
                home = os.path.expanduser("~")
                for root, dirs, files in os.walk(home):
                    # Limitar profundidad
                    if root[len(home):].count(os.sep) > 2:
                        dirs[:] = []
                        continue
                    if basename.lower() in [d.lower() for d in dirs]:
                        return os.path.join(root, basename)
                    if basename.lower() in [f.lower() for f in files]:
                        return os.path.join(root, basename)

        return resolved_path

    def _resolve_app_path(self, app_name: str) -> str:
        app_lower = app_name.strip().lower()

        if self._system == "Windows":
            if "nautilus" in app_lower:
                return "explorer.exe"
            if app_lower.endswith("/code") or app_lower == "code":
                return "code"

        target_key = app_lower
        for known_key, patterns in _KNOWN_APPS.items():
            if app_lower == known_key.lower():
                target_key = known_key
                break
            if any(p.lower() in app_lower or app_lower in p.lower() for p in patterns):
                target_key = known_key
                break
        
        if target_key in self.app_registry:
            registered_path = self.app_registry[target_key]
            if os.path.exists(registered_path):
                return registered_path
        
        which_result = shutil.which(app_name)
        if which_result:
            return which_result
        
        return app_name

    async def execute_command(self, data: dict) -> dict:
        command_id = data.get("id")
        raw_action = data.get("action")
        params = data.get("params", {})

        action_mapping = {
            "open_url": "open_url",
            "system.open_url": "open_url",
            "open_app": "open_app",
            "system.open_app": "open_app",
            "close_app": "close_app",
            "system.close_app": "close_app",
            
            "keyboard.type": "type_text",
            "type_text": "type_text",
            "keyboard.press": "press_key",
            "press_key": "press_key",
            "keyboard.hotkey": "press_hotkey",
            
            "mouse.move": "move_mouse",
            "move_mouse": "move_mouse",
            "mouse.click": "click",
            "click": "click",
            "mouse.drag": "drag_mouse",
            
            "screen.screenshot": "screenshot",
            "screenshot": "screenshot",
            "screen.ocr_screenshot": "ocr_screenshot",
            "screen.ocr_image": "ocr_image",
            "screen.find_on_screen": "find_on_screen",
            
            "window.list": "window_list",
            "window.focus": "window_focus",
            "window.close": "window_close",
        }

        action = action_mapping.get(raw_action, raw_action)
        
        try:
            result = None
            if action == "open_app":
                command = params.get("command", "").strip()
                if not command:
                    return {"id": command_id, "status": "error", "error": "No se especificó comando o aplicación"}
                
                # Chequear si en los argumentos (args) viene la ruta del documento
                args = params.get("args", [])
                if isinstance(args, list):
                    for arg in args:
                        if isinstance(arg, str):
                            arg_strip = arg.strip("\"'")
                            resolved_arg = resolve_file_path_robust(arg_strip)
                            if resolved_arg:
                                command = resolved_arg
                                break

                # Si el comando es "explorer.exe /ruta/archivo", extraer la ruta
                if "explorer" in command.lower():
                    parts = command.split()
                    for part in parts:
                        part = part.strip("\"'")
                        resolved_part = resolve_file_path_robust(part)
                        if resolved_part:
                            command = resolved_part
                            break

                import os
                resolved_file = resolve_file_path_robust(command)
                if resolved_file:
                    ext = os.path.splitext(resolved_file)[1].lower()
                    if ext in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".txt", ".csv", ".log", ".sql", ".docx", ".doc"):
                        import socket
                        import json
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(0.5)
                            s.connect(("127.0.0.1", 9876))
                            s.sendall(json.dumps({"action": "open_file", "filepath": resolved_file}).encode("utf-8"))
                            s.close()
                            return {"id": command_id, "status": "success", "result": f"Documento '{resolved_file}' enviado al visor nativo de la GUI."}
                        except Exception as e:
                            command = resolved_file

                # Si es un directorio o es una llamada a explorer sin archivo resuelto, abrir el archivo fiscal nativo
                resolved_dir = None
                if os.path.isdir(command):
                    resolved_dir = command
                else:
                    for arg in args:
                        if isinstance(arg, str):
                            arg_strip = arg.strip("\"'")
                            if os.path.isdir(arg_strip):
                                resolved_dir = arg_strip
                                break

                if resolved_dir or (command.lower() in ("explorer.exe", "explorer", "nautilus") and not resolved_file):
                    import socket
                    import json
                    try:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(0.5)
                        s.connect(("127.0.0.1", 9876))
                        s.sendall(json.dumps({"action": "open_viewer", "filepath": resolved_dir}).encode("utf-8"))
                        s.close()
                        return {"id": command_id, "status": "success", "result": "Visor de documentos abierto en la GUI nativa."}
                    except Exception as e:
                        pass

                resolved_command = self._resolve_app_path(command)
                if _IS_WINDOWS:
                    use_shell = resolved_command.lower() in ["explorer.exe", "code"] or not resolved_command.endswith(".exe")
                    subprocess.Popen(
                        resolved_command,
                        shell=use_shell,
                        creationflags=subprocess.CREATE_NO_WINDOW if not use_shell else 0
                    )
                else:
                    subprocess.Popen(resolved_command, shell=False)
                result = f"Aplicación '{command}' iniciada correctamente."
                
            elif action == "close_app":
                app_name = params.get("command", params.get("app_name", "")).strip()
                if not app_name:
                    return {"id": command_id, "status": "error", "error": "No se especificó la aplicación a cerrar"}
                
                if _IS_WINDOWS:
                    exec_name = app_name if app_name.lower().endswith(".exe") else f"{app_name}.exe"
                    subprocess.run(["taskkill", "/F", "/IM", exec_name], check=True, capture_output=True)
                    result = f"Aplicación '{app_name}' cerrada correctamente."
                else:
                    subprocess.run(["pkill", "-f", app_name], check=True, capture_output=True)
                    result = f"Aplicación '{app_name}' cerrada correctamente."
            
            elif action == "open_url":
                url = params.get("url", "").strip()
                if not url:
                    return {"id": command_id, "status": "error", "error": "URL vacía"}
                
                import os
                local_path = url
                if url.startswith("file:///"):
                    local_path = url[8:]
                local_path = local_path.strip("\"'")
                
                if os.path.exists(local_path) and os.path.isfile(local_path):
                    ext = os.path.splitext(local_path)[1].lower()
                    if ext in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".txt", ".csv", ".log", ".sql", ".docx", ".doc"):
                        import socket
                        import json
                        try:
                            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            s.settimeout(0.5)
                            s.connect(("127.0.0.1", 9876))
                            s.sendall(json.dumps({"action": "open_file", "filepath": os.path.abspath(local_path)}).encode("utf-8"))
                            s.close()
                            return {"id": command_id, "status": "success", "result": f"Documento '{local_path}' enviado al visor nativo de la GUI."}
                        except Exception as e:
                            pass
                
                asyncio.create_task(asyncio.to_thread(webbrowser.open, url))
                result = f"URL abierta: {url}"

            elif action == "type_text":
                text = params.get("text", "")
                await asyncio.to_thread(pyautogui.write, text)
                result = f"Texto escrito: {text}"
            
            elif action == "press_key":
                key = params.get("key")
                await asyncio.to_thread(pyautogui.press, key)
                result = f"Tecla presionada: {key}"

            elif action == "press_hotkey":
                keys = params.get("keys", [])
                await asyncio.to_thread(pyautogui.hotkey, *keys)
                result = f"Hotkey presionada: {keys}"

            elif action == "move_mouse":
                x = params.get("x", 0)
                y = params.get("y", 0)
                await asyncio.to_thread(pyautogui.moveTo, x, y)
                result = f"Ratón movido a ({x}, {y})"

            elif action == "click":
                button = params.get("button", "left")
                await asyncio.to_thread(pyautogui.click, button=button)
                result = f"Click realizado con botón {button}"

            elif action == "drag_mouse":
                x2 = params.get("x2", 0)
                y2 = params.get("y2", 0)
                button = params.get("button", "left")
                duration = params.get("duration", 0.5)
                await asyncio.to_thread(pyautogui.dragTo, x2, y2, button=button, duration=duration)
                result = f"Arrastre realizado a ({x2}, {y2})"

            elif action == "screenshot":
                screenshot = await asyncio.to_thread(pyautogui.screenshot)
                buffered = BytesIO()
                screenshot.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                result = {"message": "Captura de pantalla realizada.", "image_data": img_str}

            else:
                return {"id": command_id, "status": "error", "error": f"Acción desconocida: {action}"}
            return {"id": command_id, "status": "success", "result": result}
        except Exception as e:
            logger.error(f"Error ejecutando {action}: {str(e)}")
            return {"id": command_id, "status": "error", "error": str(e)}


def resolve_file_path_robust(target_path):
    if not target_path:
        return None
        
    import os
    target_path = target_path.strip("\"'")
    
    if os.path.exists(target_path) and os.path.isfile(target_path):
        return os.path.abspath(target_path)
        
    filename = os.path.basename(target_path)
    
    from pathlib import Path
    home = Path.home()
    search_dirs = [
        str(home / "Desktop" / "Facturas_Para_Procesar"),
        str(home / "Desktop" / "Facturas_Pendientes_Cobro"),
        str(home / "Desktop" / "Facturas_Emitidas"),
        "data",
        "facturas",
        "gastos"
    ]
    
    for s_dir in search_dirs:
        if os.path.exists(s_dir):
            for root, dirs, files in os.walk(s_dir):
                if filename in files:
                    return os.path.abspath(os.path.join(root, filename))
                for f in files:
                    if f.lower() == filename.lower():
                        return os.path.abspath(os.path.join(root, f))
                base_name, _ = os.path.splitext(filename)
                for f in files:
                    f_base, _ = os.path.splitext(f)
                    if base_name.lower() in f.lower() or f_base.lower() == base_name.lower():
                        return os.path.abspath(os.path.join(root, f))
    return None
