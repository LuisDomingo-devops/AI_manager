"""
assistant_thread.py -- Hilo de escucha de voz y texto de Alfonso.
Extraido de app.py. Elimina la duplicacion de _handle_tool_triggers().
"""
import os
import sys
import uuid
import asyncio
import base64
import json

from PyQt6.QtCore import QThread, pyqtSignal

from core.api_client import AlfonsoAPI
from core.processor import ResponseProcessor
from services.audio import AudioService


class AssistantThread(QThread):
    """Hilo secundario para el loop de escucha de voz y texto."""
    new_message = pyqtSignal(str, str)          # sender, message
    state_changed = pyqtSignal(str)             # idle, idle_text, listening, thinking, speaking
    agent_status_changed = pyqtSignal(str)      # connected, disconnected, error
    audio_level_updated = pyqtSignal(int, str)  # level, device_name
    open_calendar = pyqtSignal()
    close_calendar = pyqtSignal()
    sync_calendar = pyqtSignal()
    open_mail = pyqtSignal()
    close_mail = pyqtSignal()
    sync_mail = pyqtSignal()
    open_editor = pyqtSignal()
    close_editor = pyqtSignal()
    switch_session_requested = pyqtSignal(str, str, str)  # session_id, project_name, title
    confirm_invoice_requested = pyqtSignal(dict)           # datos de la factura

    def __init__(self, config):
        super().__init__()
        self.config = config

        api_key = self._load_api_key(config)
        self.api = AlfonsoAPI(config.get("url", "http://localhost:8000"), api_key)
        self.audio = AudioService()
        self.processor = ResponseProcessor()
        self.running = True
        self.session_id = self._load_or_create_session_id()
        self.text_mode = True
        self.pending_text_message = None
        self.loop = None

        self.device_name = "Dispositivo Predeterminado"
        device_id = config.get("device")
        if device_id is not None:
            for d in self.audio.list_input_devices():
                if d["index"] == device_id:
                    self.device_name = d["name"]
                    break

    # ------------------------------------------------------------------
    # Helpers privados de inicializacion
    # ------------------------------------------------------------------
    @staticmethod
    def _load_api_key(config) -> str:
        api_key = config.get("api_key", "default_key")
        try:
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            key_file = os.path.join(parent_dir, "data", ".api_key")
            if os.path.exists(key_file):
                with open(key_file, "r", encoding="utf-8") as kf:
                    api_key = kf.read().strip()
        except Exception:
            pass
        return api_key

    @staticmethod
    def _load_or_create_session_id() -> str:
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(gui_dir)
        logs_dir = os.path.join(ui_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        config_path = os.path.join(logs_dir, "session_config.json")

        session_id = None
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    session_id = json.load(f).get("session_id")
            except Exception:
                pass

        if not session_id:
            session_id = str(uuid.uuid4())
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"session_id": session_id}, f, indent=4)
            except Exception:
                pass
        return session_id

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def set_text_mode(self, enabled: bool):
        self.text_mode = enabled
        self.state_changed.emit("idle_text" if enabled else "idle")

    def send_text_message(self, message: str):
        if not message.strip():
            return
        self.pending_text_message = message

    # ------------------------------------------------------------------
    # Procesamiento de herramientas (UNICO punto, antes duplicado x2)
    # ------------------------------------------------------------------
    def _handle_tool_triggers(self, response_data: dict):
        """
        Emite las senales Qt correspondientes a cada herramienta
        devuelta por el backend. Centraliza la logica que antes
        estaba duplicada en el bloque de texto y en el de voz.
        """
        tools_to_trigger = []
        if response_data.get("type") == "multi_tool":
            for r in response_data.get("results", []):
                if r.get("tool"):
                    tools_to_trigger.append((r.get("tool"), r))
        elif response_data.get("tool"):
            tools_to_trigger.append((response_data.get("tool"), response_data))

        for tool_name, tool_ctx in tools_to_trigger:
            if tool_name == "calendar_open_ui":
                self.open_calendar.emit()
            elif tool_name == "calendar_close_ui":
                self.close_calendar.emit()
            elif tool_name in ("calendar_create_event", "calendar_delete_event", "calendar_update_event"):
                self.sync_calendar.emit()
            elif tool_name == "mail_open_ui":
                self.open_mail.emit()
            elif tool_name == "mail_close_ui":
                self.close_mail.emit()
            elif tool_name in ("mail_receive_mock_emails", "mail_classify_emails", "mail_get_unread_summary"):
                self.sync_mail.emit()
            elif tool_name == "dev_studio_open_ui":
                self.open_editor.emit()
            elif tool_name == "dev_studio_close_ui":
                self.close_editor.emit()
            elif tool_name == "switch_project_session":
                p_data = response_data.get("args") or response_data.get("result", {})
                if isinstance(p_data, dict):
                    if "result" in p_data and isinstance(p_data["result"], dict):
                        p_data = p_data["result"]
                    new_sid = p_data.get("session_id")
                    if new_sid:
                        proj_name = p_data.get("project_name") or "default"
                        title_name = p_data.get("title") or "Nueva conversacion"
                        self.switch_session_requested.emit(new_sid, proj_name, title_name)

    def _check_invoice_confirmation(self, response_data: dict):
        """Detecta si hay una factura pendiente de confirmacion humana."""
        pending_invoice = None
        if response_data.get("type") == "multi_tool":
            for r in response_data.get("results", []):
                if r.get("tool") == "generate_invoice_pdf":
                    res_tool = r.get("result", {})
                    if res_tool.get("is_draft") and "requiere la confirmacion" in res_tool.get("message", ""):
                        pending_invoice = {**r.get("args", {}), **res_tool}
        elif response_data.get("tool") == "generate_invoice_pdf":
            res_tool = response_data.get("result", {})
            if res_tool.get("is_draft") and "requiere la confirmacion" in res_tool.get("message", ""):
                pending_invoice = {**response_data.get("args", {}), **res_tool}
        if pending_invoice:
            self.confirm_invoice_requested.emit(pending_invoice)

    # ------------------------------------------------------------------
    # Loop principal (async)
    # ------------------------------------------------------------------
    async def _audio_loop(self):
        keyword = self.config.get("keyword", "alfonso").lower()
        device = self.config.get("device", None)
        output_device = self.config.get("output_device", None)

        threshold = self.config.get("threshold")
        if threshold is None:
            effective_device = device if device is not None else self.audio.device
            if hasattr(self.audio, "calibrate_threshold"):
                threshold = await asyncio.to_thread(self.audio.calibrate_threshold, effective_device)
            else:
                from core.config import SILENCE_THRESHOLD
                threshold = SILENCE_THRESHOLD
            self.config["threshold"] = threshold

        while self.running:
            try:
                if self.text_mode:
                    if self.pending_text_message:
                        user_text = self.pending_text_message
                        self.pending_text_message = None

                        self.state_changed.emit("thinking")
                        self.new_message.emit("Tu", user_text)

                        chat_res = self.api.send_chat(user_text, self.session_id)
                        response_data = chat_res.get("result", {})
                        response_text = self.processor.format_response(response_data)
                        self.new_message.emit("Alfonso", response_text)

                        self._check_invoice_confirmation(response_data)
                        self._handle_tool_triggers(response_data)

                        if response_text and "[SISTEMA: Archivos guardados con exito" in response_text:
                            self.open_editor.emit()

                        self.state_changed.emit("idle_text")
                    else:
                        self.msleep(100)
                    continue

                wav = await asyncio.to_thread(self.audio.record_chunk, 3, device=device)
                level = self.audio.get_level(wav)
                self.audio_level_updated.emit(level, self.device_name)

                if not self.audio.has_voice(wav, threshold):
                    continue

                print("[DEBUG] Voz detectada, verificando wake word...")
                if self.audio.has_voice(wav, threshold):
                    print(f"[OK] Wake word '{keyword}' detectada.")
                    self.state_changed.emit("listening")
                    self.new_message.emit("Alfonso", "Dime, te escucho...")

                    await asyncio.sleep(0.3)
                    wav_order = await asyncio.to_thread(self.audio.record_chunk, 5, device=device)
                    self.state_changed.emit("thinking")

                    print("[INFO] Procesando transcripcion local...")
                    user_text = await asyncio.to_thread(self.audio.transcribe_local, wav_order)

                    if user_text:
                        print(f"[OK] Alfonso ha entendido: '{user_text}'")
                        self.new_message.emit("Tu", user_text)

                        chat_res = await asyncio.to_thread(self.api.send_chat, user_text, self.session_id)
                        response_data = chat_res.get("result", {})
                        response_text = self.processor.format_response(response_data)
                        self.new_message.emit("Alfonso", response_text)

                        self._handle_tool_triggers(response_data)

                        if response_text and "[SISTEMA: Archivos guardados con exito" in response_text:
                            self.open_editor.emit()

                        audio_b64 = response_data.get("audio")
                        if audio_b64:
                            self.state_changed.emit("speaking")
                            audio_bytes = base64.b64decode(audio_b64)
                            await asyncio.to_thread(self.audio.play_audio, audio_bytes, device=output_device)
                        elif response_text:
                            self.state_changed.emit("speaking")
                            tts_text = response_text
                            if len(response_text) > 200:
                                tts_text = "Te he dejado la informacion detallada por escrito en el chat."
                            audio_path = await self.audio.text_to_speech_human(tts_text)
                            if audio_path:
                                await asyncio.to_thread(self.audio.play_audio_file, audio_path)
                            else:
                                audio_bytes = await asyncio.to_thread(self.audio.text_to_wav_bytes, tts_text)
                                if audio_bytes:
                                    await asyncio.to_thread(self.audio.play_audio, audio_bytes, device=output_device)
                    else:
                        print("[WARN] El audio se proceso pero no se detectaron palabras.")
                        self.new_message.emit("Alfonso", "Lo siento, no te he oido bien.")

                    print("[INFO] Volviendo a modo escucha...")
                    self.state_changed.emit("idle")

            except Exception as e:
                print(f"[ERROR] Error en el loop de audio: {e}")
                self.state_changed.emit("error")
                await asyncio.sleep(2)
                continue

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        self.state_changed.emit("connecting")
        print(f"[INFO] Intentando conectar al servidor backend: {self.api.base_url}")
        try:
            if not self.api.ping():
                print(f"[ERROR] No se pudo conectar al backend {self.api.base_url}.")
                self.state_changed.emit("error")
                return
            print("[OK] Conexion con el servidor backend establecida.")
        except Exception as e:
            print(f"[CRITICAL] Error durante la conexion al backend: {e}")
            self.state_changed.emit("error")
            return

        self.state_changed.emit("idle")
        try:
            self.loop.run_until_complete(self._audio_loop())
        except asyncio.CancelledError:
            print("[INFO] AssistantThread tasks cancelled.")
        finally:
            self.loop.close()
            print("[INFO] Asyncio event loop closed.")

    def stop(self):
        self.running = False
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(
                lambda: [task.cancel() for task in asyncio.all_tasks(self.loop)]
            )
        self.wait(200)
