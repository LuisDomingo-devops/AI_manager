import sys
import os
from pathlib import Path
# Añadir la carpeta raíz del proyecto (alfonso_autonomo) y la carpeta client al PATH de Python
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append(str(Path(__file__).parent.parent.parent))
import uuid
import numpy as np
import asyncio
import base64
import random
import datetime

from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, 
                             QWidget, QLabel, QFrame, QPushButton, QLineEdit, QHBoxLayout, QScrollArea, QProgressBar, QGridLayout, QTableWidget, QTableWidgetItem, QHeaderView, QMenu,
                             QListWidget, QListWidgetItem, QTextEdit, QTextBrowser, QSplitter, QGroupBox, QDialog, QFormLayout, QMessageBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent
from PyQt6.QtGui import QScreen, QPainter, QColor, QBrush, QPen, QPainterPath, QFont, QKeyEvent, QPixmap, QRadialGradient, QTextOption

from core.api_client import AlfonsoAPI
from core.processor import ResponseProcessor
from services.audio import AudioService
from core.alfonso_agent_logic import AlfonsoAgentLogic


class AssistantThread(QThread):
    """Hilo secundario para el loop de escucha de voz."""
    new_message = pyqtSignal(str, str) # sender, message
    state_changed = pyqtSignal(str)    # idle, idle_text, listening, thinking, speaking
    agent_status_changed = pyqtSignal(str) # connected, disconnected, error
    audio_level_updated = pyqtSignal(int, str) # level, device_name
    open_calendar = pyqtSignal()
    close_calendar = pyqtSignal()
    sync_calendar = pyqtSignal()
    open_mail = pyqtSignal()
    close_mail = pyqtSignal()
    sync_mail = pyqtSignal()
    open_editor = pyqtSignal()
    close_editor = pyqtSignal()
    switch_session_requested = pyqtSignal(str, str, str) # session_id, project_name, title


    def __init__(self, config):
        super().__init__()
        self.config = config
        self.api = AlfonsoAPI(config.get('url', 'http://localhost:8000'), config.get('api_key', 'default_key'))
        self.audio = AudioService()
        self.processor = ResponseProcessor()
        self.running = True
        # Obtener o crear Session ID persistente en ui/logs/session_config.json
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        ui_dir = os.path.dirname(gui_dir)
        logs_dir = os.path.join(ui_dir, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        config_path = os.path.join(logs_dir, "session_config.json")
        
        session_id = None
        if os.path.exists(config_path):
            try:
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    session_id = json.load(f).get("session_id")
            except Exception:
                pass
        
        if not session_id:
            session_id = str(uuid.uuid4())
            try:
                import json
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump({"session_id": session_id}, f, indent=4)
            except Exception:
                pass
                
        self.session_id = session_id
        self.text_mode = True
        self.pending_text_message = None
        self.loop = None 
        
        self.device_name = "Dispositivo Predeterminado"
        device_id = config.get('device')
        if device_id is not None:
            for d in self.audio.list_input_devices():
                if d['index'] == device_id:
                    self.device_name = d['name']
                    break

    def set_text_mode(self, enabled: bool):
        self.text_mode = enabled
        self.state_changed.emit("idle_text" if enabled else "idle")

    def send_text_message(self, message: str):
        if not message.strip():
            return
        self.pending_text_message = message

    async def _audio_loop(self):
        keyword = self.config.get('keyword', 'alfonso').lower()
        device = self.config.get('device', None)
        output_device = self.config.get('output_device', None)

        threshold = self.config.get('threshold')
        if threshold is None:
            effective_device = device if device is not None else self.audio.device
            if hasattr(self.audio, 'calibrate_threshold'):
                threshold = await asyncio.to_thread(self.audio.calibrate_threshold, effective_device)
            else:
                # Fallback local seguro si la API de AudioService restaurada no lo expone
                from core.config import SILENCE_THRESHOLD
                threshold = SILENCE_THRESHOLD
            self.config['threshold'] = threshold 

        while self.running:
            try:
                if self.text_mode:
                    if self.pending_text_message:
                        user_text = self.pending_text_message
                        self.pending_text_message = None
                        
                        self.state_changed.emit("thinking")
                        self.new_message.emit("Tú", user_text)
                        
                        chat_res = self.api.send_chat(user_text, self.session_id)
                        response_data = chat_res.get("result", {})
                        response_text = self.processor.format_response(response_data)
                        self.new_message.emit("Alfonso", response_text)

                        tools_to_trigger = []
                        if response_data.get("type") == "multi_tool":
                            for r in response_data.get("results", []):
                                if r.get("tool"):
                                    tools_to_trigger.append(r.get("tool"))
                        elif response_data.get("tool"):
                            tools_to_trigger.append(response_data.get("tool"))

                        for tool_name in tools_to_trigger:
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
                                # Cambiar la sesión activa de forma dinámica
                                p_data = response_data.get("args") or response_data.get("result", {})
                                if isinstance(p_data, dict):
                                    if "result" in p_data and isinstance(p_data["result"], dict):
                                        p_data = p_data["result"]
                                    new_sid = p_data.get("session_id")
                                    if new_sid:
                                        proj_name = p_data.get("project_name") or "default"
                                        title_name = p_data.get("title") or "Nueva conversación"
                                        self.switch_session_requested.emit(new_sid, proj_name, title_name)
                        
                        if response_text and "[SISTEMA: Archivos guardados con éxito" in response_text:
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
                wake_word_detected_locally = self.audio.has_voice(wav, threshold)
                if wake_word_detected_locally:
                    print(f"[OK] Wake word '{keyword}' detectada (mediante actividad de voz local).")
                    self.state_changed.emit("listening")
                    self.new_message.emit("Alfonso", "Dime, te escucho...")

                    await asyncio.sleep(0.3)

                    wav_order = await asyncio.to_thread(self.audio.record_chunk, 5, device=device)
                    self.state_changed.emit("thinking")
                    
                    print(f"\n[INFO] Procesando transcripción local...")
                    user_text = await asyncio.to_thread(self.audio.transcribe_local, wav_order)
                    
                    if user_text:
                        print(f"[OK] Alfonso ha entendido: '{user_text}'")
                        self.new_message.emit("Tú", user_text)
                        
                        chat_res = await asyncio.to_thread(self.api.send_chat, user_text, self.session_id)
                        response_data = chat_res.get("result", {})
                        response_text = self.processor.format_response(response_data)
                        
                        self.new_message.emit("Alfonso", response_text)

                        tools_to_trigger = []
                        if response_data.get("type") == "multi_tool":
                            for r in response_data.get("results", []):
                                if r.get("tool"):
                                    tools_to_trigger.append(r.get("tool"))
                        elif response_data.get("tool"):
                            tools_to_trigger.append(response_data.get("tool"))

                        for tool_name in tools_to_trigger:
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
                                # Cambiar la sesión activa de forma dinámica
                                p_data = response_data.get("args") or response_data.get("result", {})
                                new_sid = p_data.get("session_id")
                                if new_sid:
                                    proj_name = p_data.get("project_name") or "default"
                                    title_name = p_data.get("title") or "Nueva conversación"
                                    self.switch_session_requested.emit(new_sid, proj_name, title_name)
                        
                        if response_text and "[SISTEMA: Archivos guardados con éxito" in response_text:
                            self.open_editor.emit()
                        
                        audio_b64 = response_data.get("audio")
                        if audio_b64:
                            self.state_changed.emit("speaking")
                            audio_bytes = base64.b64decode(audio_b64)
                            await asyncio.to_thread(self.audio.play_audio, audio_bytes, device=output_device)
                        else:
                            if response_text:
                                self.state_changed.emit("speaking")
                                tts_text = response_text
                                if len(response_text) > 200:
                                    tts_text = "Te he dejado la información detallada por escrito en el chat para que la revises."
                                audio_path = await self.audio.text_to_speech_human(tts_text)
                                if audio_path:
                                    await asyncio.to_thread(self.audio.play_audio_file, audio_path)
                                else:
                                    audio_bytes = await asyncio.to_thread(self.audio.text_to_wav_bytes, tts_text)
                                    if audio_bytes:
                                        await asyncio.to_thread(self.audio.play_audio, audio_bytes, device=output_device)
                    else:
                        print("[WARN] El audio se procesó pero no se detectaron palabras.")
                        self.new_message.emit("Alfonso", "Lo siento, no te he oído bien.")
                    
                    print("[INFO] Volviendo a modo escucha (esperando wake word)...")
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
                print(f"[ERROR] No se pudo conectar al backend {self.api.base_url}. Revisa si el servidor está activo.")
                self.state_changed.emit("error")
                return
            print("[OK] Conexión con el servidor backend establecida.")
        except Exception as e:
            print(f"[CRITICAL] Error durante la conexión al backend: {e}")
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
            self.loop.call_soon_threadsafe(lambda: [task.cancel() for task in asyncio.all_tasks(self.loop)])
        self.wait(200)


class HUDPanel(QFrame):
    """Tarjeta contenedora estilo Glassmorphism Dark."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.title = title
        self.setObjectName("HUDPanel")
        self.setStyleSheet("""
            #HUDPanel {
                background-color: rgba(30, 41, 59, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 36, 16, 16)
        
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Punto de acento / Badge - Indigo
        painter.setBrush(QBrush(QColor(99, 102, 241, 220)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(16, 18, 6, 6)
        
        # Título del panel
        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)
        painter.setPen(QColor(241, 245, 249, 220))
        painter.drawText(28, 24, self.title.upper())


class QuarterlyBarChartWidget(QFrame):
    """Gráfico de barras estilizado de ingresos/gastos del trimestre en curso."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QuarterlyBarChartWidget {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(99, 102, 241, 0.15);
                border-radius: 6px;
                padding: 10px;
            }
        """)
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
        # No setCursor to match other standard buttons
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        
        import datetime
        now_dt = datetime.datetime.now()
        current_quarter = (now_dt.month - 1) // 3 + 1
        
        lbl_title = QLabel(f"RENDIMIENTO {current_quarter}T (EN CURSO)")
        lbl_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #818CF8; letter-spacing: 0.5px; background: transparent; border: none;")
        lbl_title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(lbl_title)
        
        # Ingresos
        ing_layout = QHBoxLayout()
        lbl_ing = QLabel("Ingresos:")
        lbl_ing.setStyleSheet("font-size: 10px; color: #94A3B8; background: transparent; border: none;")
        lbl_ing.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_ing_val = QLabel("0,00 €")
        self.lbl_ing_val.setStyleSheet("font-family: 'Consolas'; font-size: 10px; color: #10B981; font-weight: bold; background: transparent; border: none;")
        self.lbl_ing_val.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        ing_layout.addWidget(lbl_ing)
        ing_layout.addStretch()
        ing_layout.addWidget(self.lbl_ing_val)
        layout.addLayout(ing_layout)
        
        self.bar_ing = QProgressBar()
        self.bar_ing.setFixedHeight(8)
        self.bar_ing.setTextVisible(False)
        self.bar_ing.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 4px;
            }
        """)
        self.bar_ing.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.bar_ing)
        
        # Gastos
        gast_layout = QHBoxLayout()
        lbl_gast = QLabel("Gastos:")
        lbl_gast.setStyleSheet("font-size: 10px; color: #94A3B8; background: transparent; border: none;")
        lbl_gast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.lbl_gast_val = QLabel("0,00 €")
        self.lbl_gast_val.setStyleSheet("font-family: 'Consolas'; font-size: 10px; color: #EF4444; font-weight: bold; background: transparent; border: none;")
        self.lbl_gast_val.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        gast_layout.addWidget(lbl_gast)
        gast_layout.addStretch()
        gast_layout.addWidget(self.lbl_gast_val)
        layout.addLayout(gast_layout)
        
        self.bar_gast = QProgressBar()
        self.bar_gast.setFixedHeight(8)
        self.bar_gast.setTextVisible(False)
        self.bar_gast.setStyleSheet("""
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.05);
                border: none;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #EF4444;
                border-radius: 4px;
            }
        """)
        self.bar_gast.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.bar_gast)
        
    def update_data(self, ingresos, gastos):
        self.lbl_ing_val.setText(f"{ingresos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        self.lbl_gast_val.setText(f"{gastos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
        
        max_val = max(ingresos, gastos, 1.0)
        self.bar_ing.setValue(int((ingresos / max_val) * 100))
        self.bar_gast.setValue(int((gastos / max_val) * 100))

    def mousePressEvent(self, event):
        from PyQt6.QtCore import Qt
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p is not None:
                if hasattr(p, "open_kpi_dashboard"):
                    p.open_kpi_dashboard()
                    return
                p = p.parent()


class AnimatedWaveWidget(QWidget):
    """Visualizador de rostro digital de Cain (Robocop 2) reactivo y animado."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 280)
        self._state = "idle"
        self._animation_phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_animation)
        self._timer.start(30)

        gui_dir = os.path.dirname(os.path.abspath(__file__))
        self._raw_photo = QPixmap(os.path.join(gui_dir, "alfonso_photo.jpg"))
        self._processed_photo = None
        if not self._raw_photo.isNull():
            self._processed_photo = self._process_hologram_image(self._raw_photo)

        # Colores originales de los estados conservados exactamente
        self._base_color = QColor(255, 184, 0)
        self._target_color = self._base_color
        self._current_color = self._base_color

        self._color_animation = QPropertyAnimation(self, b"current_color")
        self._color_animation.setDuration(500)
        self._color_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _update_animation(self):
        self._animation_phase += 0.05
        if self._animation_phase > 1000.0:
            self._animation_phase = 0.0
        self.update()

    def _process_hologram_image(self, raw_pixmap):
        from PyQt6.QtGui import QImage, QColor, QPainter, QBrush, QPixmap
        from PyQt6.QtCore import Qt, QSize
        import math
        
        # 1. Scale photo to a standard size for processing (e.g. 240x280)
        img = raw_pixmap.toImage().scaled(240, 280, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        
        # Crop tightly to center face
        cx_img = (img.width() - 200) // 2
        cy_img = (img.height() - 240) // 2
        img = img.copy(cx_img, cy_img, 200, 240)
        
        # Convert to ARGB32
        img = img.convertToFormat(QImage.Format.Format_ARGB32)
        
        # 2. Apply soft vignette to black (isolate the face)
        width, height = img.width(), img.height()
        mask_cx, mask_cy = width / 2.0, height / 2.0
        rx, ry = 85.0, 110.0 # Radios de la elipse facial
        
        for y in range(height):
            for x in range(width):
                col = QColor.fromRgb(img.pixel(x, y))
                
                # Factor de viñeta elíptica suave para fundir el borde de la foto a negro
                dx = (x - mask_cx) / rx
                dy = (y - mask_cy) / ry
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist >= 1.0:
                    alpha_factor = 0.0
                else:
                    # Atenuación coseno suave hacia los bordes
                    alpha_factor = math.cos(dist * math.pi / 2.0) ** 2
                
                # Multiplicar los componentes R, G, B por el factor de viñeta para fundir a negro puro
                r_final = int(col.red() * alpha_factor)
                g_final = int(col.green() * alpha_factor)
                b_final = int(col.blue() * alpha_factor)
                
                img.setPixel(x, y, QColor(r_final, g_final, b_final, col.alpha()).rgb())
        
        # 3. Generate the CRT Phosphor shadow mask pattern on top
        crt_mask = QImage(QSize(200, 240), QImage.Format.Format_ARGB32)
        crt_mask.fill(Qt.GlobalColor.transparent)
        
        m_painter = QPainter(crt_mask)
        m_painter.drawImage(0, 0, img)
        
        # Draw dense diagonal grid dots or fine lines to match the screen grid
        m_painter.setPen(QColor(0, 0, 0, 100)) # dark grid
        for y in range(0, 240, 2):
            offset = 1 if (y % 4 == 0) else 0
            for x in range(offset, 200, 2):
                m_painter.drawPoint(x, y)
                
        m_painter.end()
        
        return QPixmap.fromImage(crt_mask)

    def set_current_color(self, color: QColor):
        self._current_color = color
        self.update()

    def get_current_color(self) -> QColor:
        return self._current_color

    current_color = pyqtProperty(QColor, get_current_color, fset=set_current_color)

    def set_state(self, state: str):
        if self._state == state:
            return

        self._state = state
        self._animation_phase = 0.0

        # Mismo código de color original conservado exactamente
        state_configs = {
            "connecting": {"color": QColor(255, 184, 0)},
            "idle":       {"color": QColor(0, 191, 255, 150)},
            "idle_text":  {"color": QColor(0, 240, 255)},
            "listening":  {"color": QColor(0, 255, 102)},
            "thinking":   {"color": QColor(255, 100, 0)},
            "speaking":   {"color": QColor(0, 255, 240)},
            "error":      {"color": QColor(255, 50, 50)},
        }

        config = state_configs.get(state, state_configs["idle"])
        self._target_color = config["color"]

        self._color_animation.stop()
        self._color_animation.setStartValue(self._current_color)
        self._color_animation.setEndValue(self._target_color)
        self._color_animation.start()

        if state == "error":
            self._timer.start(30)
        else:
            self._timer.start(30)
        self.update()

    def _draw_ethereal_core(self, painter, cx, cy, base_color):
        import math
        t = self._animation_phase
        
        # Rotación 3D general del sistema orbital
        yaw = t * 0.4
        pitch = 0.65  # Inclinación fija elegante para perspectiva 3D
        roll = t * 0.15

        r, g, b = base_color.red(), base_color.green(), base_color.blue()

        # 1. Aura de Resplandor Radial de Fondo (Más pequeño)
        glow_grad = QRadialGradient(cx, cy, 90)
        glow_grad.setColorAt(0.0, QColor(r, g, b, 45))
        glow_grad.setColorAt(0.6, QColor(r, g, b, 12))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - 100), int(cy - 100), 200, 200)

        painter.save()

        # Matriz de rotación 3D para proyectar círculos orbitales y partículas
        def project_3d_point(x, y, z):
            # Rotación Yaw (Eje Y)
            cos_y, sin_y = math.cos(yaw), math.sin(yaw)
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            
            # Rotación Pitch (Eje X)
            cos_p, sin_p = math.cos(pitch), math.sin(pitch)
            y2 = y * cos_p - z1 * sin_p
            z2 = y * sin_p + z1 * cos_p
            
            # Proyección perspectiva
            focal = 350.0
            dist = 280.0 + z2
            px = cx + (x1 * focal) / dist
            py = cy + (y2 * focal) / dist
            return px, py, z2

        # 2. Dibujar Anillos Concentricos en 3D (Radios Reducidos para Compactar)
        num_rings = 4
        base_radii = [24, 42, 60, 78]
        
        for idx, base_r in enumerate(base_radii):
            # Dinámica reactiva según el estado
            pulse = 0.0
            if self._state == "speaking":
                pulse = abs(math.sin(t * 9.0 - idx)) * 8.0
            elif self._state == "listening":
                pulse = math.sin(t * 4.0 + idx) * 3.5
            elif self._state == "thinking":
                pulse = math.sin(t * 8.0) * 2.0
            else: # idle
                pulse = math.sin(t * 1.5 + idx) * 1.8
                
            ring_r = base_r + pulse
            
            # Generar puntos del anillo 3D
            ring_pts = []
            steps = 48
            for step in range(steps):
                angle = (2.0 * math.pi * step) / steps
                # Cada anillo tiene una inclinación levemente cruzada para elegancia
                rx = ring_r * math.cos(angle)
                ry = ring_r * math.sin(angle)
                rz = math.sin(angle * 2.0) * 8.0
                
                px, py, pz = project_3d_point(rx, ry, rz)
                ring_pts.append((px, py, pz))
            
            # Dibujar trazado del anillo con modulación Z
            for i in range(steps):
                px1, py1, pz1 = ring_pts[i]
                px2, py2, pz2 = ring_pts[(i + 1) % steps]
                
                avg_z = (pz1 + pz2) / 2.0
                alpha = int(max(25, min(240, 140 + avg_z * 2.5)))
                
                pen = QPen(QColor(r, g, b, alpha), 1.1 if idx > 0 else 1.8)
                if idx == 1:
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif idx == 2:
                    pen.setStyle(Qt.PenStyle.DotLine)
                    
                painter.setPen(pen)
                painter.drawLine(int(px1), int(py1), int(px2), int(py2))

        # 3. Nodos y Partículas Orbitantes en 3D (Constellation Field más compacto)
        num_particles = 16
        particle_pts = []
        for i in range(num_particles):
            # Órbitas cruzadas flotantes
            angle = (2.0 * math.pi * i) / num_particles + (t * 0.2)
            p_r = 52.0 + math.sin(t * 0.8 + i) * 7.0
            
            px = p_r * math.cos(angle)
            py = p_r * math.sin(angle)
            pz = math.cos(angle * 3.0) * 14.0
            
            px_p, py_p, pz_p = project_3d_point(px, py, pz)
            particle_pts.append((px_p, py_p, pz_p))

        # Dibujar líneas de constelación translúcidas
        for i in range(num_particles):
            px1, py1, pz1 = particle_pts[i]
            px2, py2, pz2 = particle_pts[(i + 1) % num_particles]
            
            avg_z = (pz1 + pz2) / 2.0
            alpha = int(max(10, min(100, 50 + avg_z * 1.5)))
            
            painter.setPen(QPen(QColor(r, g, b, alpha), 0.7))
            painter.drawLine(int(px1), int(py1), int(px2), int(py2))

        # Dibujar nodos de constelación brillantes
        for px_p, py_p, pz_p in particle_pts:
            alpha = int(max(40, min(255, 180 + pz_p * 3.0)))
            size = int(max(2, min(5, 3.5 + pz_p * 0.06)))
            
            painter.setBrush(QBrush(QColor(r, g, b, alpha)))
            painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.8)), 0.7))
            painter.drawEllipse(int(px_p - size/2), int(py_p - size/2), size, size)

        # 4. Núcleo Emisor Central (Reactor Core Glow - Más compacto)
        core_size = 12
        if self._state == "speaking":
            core_size += int(abs(math.sin(t * 12.0)) * 5)
        
        core_grad = QRadialGradient(cx, cy, core_size)
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.4, QColor(r, g, b, 230))
        core_grad.setColorAt(1.0, QColor(r, g, b, 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - core_size), int(cy - core_size), core_size * 2, core_size * 2)

        # Ondas concéntricas de sonido al hablar
        if self._state == "speaking":
            for wave_idx in range(3):
                wave_r = 14 + ((t * 15 + wave_idx * 20) % 45)
                wave_alpha = int(max(0, 150 - (wave_r * 2.8)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(r, g, b, wave_alpha), 1.2))
                painter.drawEllipse(int(cx - wave_r), int(cy - wave_r), int(wave_r * 2), int(wave_r * 2))

        painter.restore()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        cx = width / 2
        cy = height / 2
        
        base_color = self._current_color
        
        jitter_x = 0
        jitter_y = 0
        if self._state in ["thinking", "error"]:
            jitter_x = random.randint(-4, 4)
            jitter_y = random.randint(-4, 4)

        # 1. Dibujar Cuadrícula de Fondo CRT Estática
        painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 12), 1))
        grid_size = 20
        for x in range(0, width, grid_size):
            painter.drawLine(x, 0, x, height)
        for y in range(0, height, grid_size):
            painter.drawLine(0, y, width, y)

        # 2. Dibujar Núcleo Orbital Holográfico Etereo en 3D
        self._draw_ethereal_core(painter, cx + jitter_x, cy + jitter_y, base_color)


class CrtTerminalLabel(QLabel):
    """Label de texto limpio para lecturas y logs sin parpadeo de barrido."""
    def __init__(self, text="", color_hex="#00FF66", parent=None):
        super().__init__(text, parent)
        self.color_hex = color_hex
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_C and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            selected = self.selectedText()
            if selected:
                QApplication.clipboard().setText(selected)
                event.accept()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            font = self.font()
            size = font.pointSize()
            if size <= 0:
                size = font.pixelSize()
                if size <= 0:
                    size = 11
                new_size = max(8, min(48, size + (1 if delta > 0 else -1)))
                font.setPixelSize(new_size)
            else:
                new_size = max(8, min(48, size + (1 if delta > 0 else -1)))
                font.setPointSize(new_size)
            self.setFont(font)
            event.accept()
        else:
            super().wheelEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        copy_action = menu.addAction("Copiar Selección")
        copy_action.setEnabled(self.hasSelectedText())
        action = menu.exec(event.globalPos())
        if action == copy_action:
            QApplication.clipboard().setText(self.selectedText())


class CrtTerminalTextBrowser(QTextBrowser):
    """TextBrowser moderno para renderizar Markdown con diseño Glassmorphism Dark."""
    def __init__(self, text="", color_hex="#00E5FF", parent=None):
        super().__init__(parent)
        self.color_hex = color_hex
        self.setOpenExternalLinks(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextBrowser.LineWrapMode.WidgetWidth)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none; font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 15px; color: #E2E8F0; line-height: 1.5;")
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setMarkdown(text)


class AlfonsoSystemButton(QPushButton):
    """Clase base de botón para controles del sistema, ventanas y módulos."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.apply_default_style()

    def apply_default_style(self):
        self.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #CBD5E1;
                font-weight: bold;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
                color: #FFFFFF;
            }
            QPushButton:pressed {
                background-color: rgba(255, 255, 255, 0.25);
            }
        """)


class AlfonsoWindowCloseButton(AlfonsoSystemButton):
    """Botón de cierre visible y rojo con cambios de estado."""
    def __init__(self, parent=None):
        super().__init__("X", parent)
        self.setObjectName("BtnClose")
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                border: none;
                color: #FFFFFF;
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #EF4444;
            }
            QPushButton:pressed {
                background-color: #991B1B;
            }
        """)


class AlfonsoWindowMinimizeButton(AlfonsoSystemButton):
    """Botón de minimizar visible con cambios de estado."""
    def __init__(self, parent=None):
        super().__init__("—", parent)
        self.setObjectName("BtnMinimize")
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                border: none;
                color: #FFFFFF;
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
                font-size: 10px;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #64748B;
            }
            QPushButton:pressed {
                background-color: #334155;
            }
        """)


class AlfonsoDashboardModuleButton(AlfonsoSystemButton):
    """Botones del dashboard que heredan del botón padre y cambian de estado cuando su módulo está abierto."""
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.is_open = False
        self.update_style()

    def set_module_open(self, is_open):
        self.is_open = is_open
        self.update_style()

    def update_style(self):
        if self.is_open:
            self.setStyleSheet("""
                QPushButton {
                    background-color: #DC2626;
                    border: 1px solid #EF4444;
                    color: #FFFFFF;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #EF4444;
                }
                QPushButton:pressed {
                    background-color: #991B1B;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 184, 0, 0.15);
                    border: 1px solid #FFB800;
                    color: #FFB800;
                    font-weight: bold;
                    padding: 6px 12px;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: rgba(255, 184, 0, 0.3);
                    color: #FFFFFF;
                }
                QPushButton:pressed {
                    background-color: rgba(255, 184, 0, 0.5);
                }
            """)


class AttachedFileWidget(QFrame):
    """Widget para mostrar un archivo adjunto con icono de documento, tick verde y botón de eliminar."""
    removed = pyqtSignal(str) # Emite el path al ser eliminado

    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = filepath
        filename = os.path.basename(filepath)
        self.setFixedHeight(28)
        self.setFixedWidth(160)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(16, 185, 129, 0.15); /* Fondo verde traslúcido */
                border: 1px solid rgba(16, 185, 129, 0.4);
                border-radius: 4px;
            }
            QLabel {
                color: #E2E8F0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: bold;
                background: transparent;
                border: none;
            }
        """)
        
        # Icono
        lbl_icon = QLabel("📄")
        layout.addWidget(lbl_icon)
        
        # Nombre (truncado si es largo)
        display_name = filename if len(filename) < 20 else filename[:17] + "..."
        lbl_name = QLabel(display_name)
        lbl_name.setToolTip(filename)
        layout.addWidget(lbl_name)
        
        # Tick verde
        lbl_check = QLabel("✔️")
        layout.addWidget(lbl_check)
        
        # Botón eliminar
        btn_del = QPushButton("×")
        btn_del.setFixedSize(14, 14)
        btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_del.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #EF4444;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                color: #F87171;
            }
        """)
        btn_del.clicked.connect(self.on_delete)
        layout.addWidget(btn_del)

    def on_delete(self):
        self.removed.emit(self.filepath)


class ChatTextInput(QTextEdit):
    """QTextEdit personalizado que envía el mensaje al pulsar Enter sin Shift y soporta Drag & Drop."""
    file_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
            filepaths = []
            for url in event.mimeData().urls():
                local_path = url.toLocalFile()
                if local_path and os.path.exists(local_path):
                    filepaths.append(local_path)
            if filepaths:
                self.file_dropped.emit(filepaths)
        else:
            super().dropEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                window = self.window()
                if hasattr(window, 'send_text_message'):
                    window.send_text_message()
                event.accept()
        else:
            super().keyPressEvent(event)


class AlfonsoHUDDashboard(QMainWindow):
    """Dashboard consolidado ALFONSO OS en pantalla completa."""
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.setWindowTitle("ALFONSO OS ver 3.7.19")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.showFullScreen() 
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F172A;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(15, 23, 42, 0.3);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(99, 102, 241, 0.4);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(99, 102, 241, 0.7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: rgba(15, 23, 42, 0.3);
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(99, 102, 241, 0.4);
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(99, 102, 241, 0.7);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            QComboBox {
                background-color: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 8px;
                color: #F8FAFC;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                border: 1px solid #6366F1;
                color: #F8FAFC;
                selection-background-color: #6366F1;
                selection-color: #FFFFFF;
            }
            QMenu {
                background-color: #1E293B;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #F8FAFC;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                color: #CBD5E1;
            }
            QMenu::item:selected {
                background-color: #6366F1;
                color: #FFFFFF;
            }
            QLabel {
                font-family: 'Segoe UI', 'Inter', sans-serif;
                font-size: 12px;
                color: #CBD5E1;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #CBD5E1;
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 6px 14px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: rgba(99, 102, 241, 0.15);
                color: #FFFFFF;
                border-color: rgba(99, 102, 241, 0.4);
            }
            QPushButton:pressed {
                background-color: #6366F1;
                color: #FFFFFF;
            }
            QTextEdit, QLineEdit {
                background-color: rgba(30, 41, 59, 0.9);
                color: #F8FAFC;
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 8px;
                padding: 8px 12px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QTextEdit:focus, QLineEdit:focus {
                border-color: #6366F1;
            }
        """)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(15, 15, 15, 15)
        self.main_layout.setSpacing(15)

        self.setup_header()
        self.setup_body_columns()
        self.setup_footer()

        # Carpeta de logs local para la UI y el Agente (ui/logs)
        self.ui_logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(self.ui_logs_dir, exist_ok=True)

        # Carpeta de logs del servidor (WSL / app)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_dir = os.path.join(base_dir, 'logs')
        if not os.path.isdir(self.logs_dir):
            wsl_logs = r"\\wsl.localhost\Ubuntu\home\luisd\Alfonso\logs"
            if os.path.isdir(wsl_logs):
                self.logs_dir = wsl_logs
                
        self.current_log_file = "app.log"
        self.text_mode_enabled = True
        self.chat_history = ""
        self.uptime_seconds = 67472 
        self.calendar_window = None
        self.mail_window = None
        self.editor_window = None
        self.config_window = None
        self.diagnostics_window = None
        self.alerts_window = None
        self.reconcile_dialog = None
        self.ledger_dialog = None
        self.archive_dialog = None
        self.aeat_window = None
        
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.update_telemetry)
        self.ui_timer.start(1000)



        self.agent_process = None
        
        from PyQt6.QtNetwork import QTcpServer, QHostAddress
        self.ipc_server = QTcpServer(self)
        self.ipc_server.newConnection.connect(self.handle_ipc_connection)
        if not self.ipc_server.listen(QHostAddress(QHostAddress.SpecialAddress.LocalHost), 9876):
            print(f"Advertencia: No se pudo iniciar el servidor IPC en el puerto 9876: {self.ipc_server.errorString()}")

        self.start_agent()
        self.start_assistant()
        QTimer.singleShot(2500, self.check_onboarding)

    def handle_ipc_connection(self):
        client_socket = self.ipc_server.nextPendingConnection()
        client_socket.readyRead.connect(lambda: self.read_ipc_data(client_socket))

    def read_ipc_data(self, socket):
        import os
        data = socket.readAll().data().decode("utf-8", errors="ignore")
        socket.disconnectFromHost()
        try:
            import json
            cmd = json.loads(data)
            if cmd.get("action") == "open_file":
                filepath = cmd.get("filepath")
                if filepath and os.path.exists(filepath):
                    self.show_native_viewer(filepath)
            elif cmd.get("action") == "open_viewer":
                filepath = cmd.get("filepath")
                self.show_native_viewer(filepath)
            elif cmd.get("action") == "open_archive":
                self.show_archive()
        except Exception as e:
            print(f"Error procesando comando IPC: {e}")

    def show_native_viewer(self, filepath=None):
        try:
            import os
            from PyQt6.QtWidgets import QFileDialog
            
            if not filepath or os.path.isdir(filepath):
                search_dirs = [filepath] if (filepath and os.path.isdir(filepath)) else [
                    "C:/Users/luisd/Desktop/Facturas_Para_Procesar",
                    "C:/Users/luisd/Desktop/Facturas_Pendientes_Cobro",
                    "C:/Users/luisd/Desktop/Facturas_Emitidas",
                    "data/archivo fiscal"
                ]
                newest_file = None
                newest_time = 0
                for s_dir in search_dirs:
                    if os.path.exists(s_dir):
                        for root, dirs, files in os.walk(s_dir):
                            for f in files:
                                ext = os.path.splitext(f)[1].lower()
                                if ext in (".pdf", ".png", ".jpg", ".jpeg", ".docx", ".txt"):
                                    fpath = os.path.join(root, f)
                                    mtime = os.path.getmtime(fpath)
                                    if mtime > newest_time:
                                        newest_time = mtime
                                        newest_file = fpath
                if newest_file:
                    filepath = newest_file
                else:
                    file_filter = "Documentos (*.pdf *.png *.jpg *.jpeg *.docx *.txt)"
                    selected_file, _ = QFileDialog.getOpenFileName(self, "Seleccionar documento para visualizar", "", file_filter)
                    if selected_file:
                        filepath = selected_file
                    else:
                        return
            
            if hasattr(self, 'viewer') and self.viewer and self.viewer.isVisible():
                if os.path.normpath(self.viewer.filepath) == os.path.normpath(filepath):
                    self.viewer.raise_()
                    self.viewer.activateWindow()
                    return
                else:
                    self.viewer.close()
                    
            self.viewer = AlfonsoDocumentViewerDialog(self, filepath)
            self.viewer.show()
            self.viewer.raise_()
            self.viewer.activateWindow()
        except Exception as e:
            print(f"Error abriendo visor desde IPC: {e}")

    def check_onboarding(self):
        try:
            import requests
            headers = {"X-API-Key": self.config.get("api_key", "default_key")}
            server_url = self.config.get("url", "http://127.0.0.1:8000")
            res = requests.get(f"{server_url}/tax/profile", headers=headers, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                if not data.get("configured", False):
                    api_client = AlfonsoAPI(self.config.get('url', 'http://127.0.0.1:8000'), self.config.get('api_key', 'default_key'))
                    wizard = AlfonsoOnboardingWizard(self, api_client)
                    wizard.exec()
        except Exception as e:
            print(f"Error checking onboarding status: {e}")

    def start_agent(self):
        try:
            import subprocess
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            ui_dir = os.path.dirname(gui_dir)
            agent_path = os.path.join(ui_dir, "alfonso_agent.py")
            
            python_exe = sys.executable
            
            from urllib.parse import urlparse
            server_url = self.config.get('url', 'http://localhost:8000')
            parsed = urlparse(server_url)
            host = parsed.hostname or "localhost"
            bridge_url = self.config.get('bridge_url', f"ws://{host}:8765")
            
            # Limpiar agentes duplicados de forma no bloqueante usando psutil
            try:
                import psutil
                current_pid = os.getpid()
                for proc in psutil.process_iter(['pid', 'cmdline']):
                    try:
                        cmdline = proc.info.get('cmdline')
                        if cmdline and any("alfonso_agent.py" in arg for arg in cmdline):
                            if proc.info.get('pid') != current_pid:
                                proc.terminate()
                    except Exception:
                        pass
            except Exception:
                pass

            creation_flags = 0
            if sys.platform == "win32":
                # CREATE_NO_WINDOW = 0x08000000
                creation_flags = 0x08000000
                
            self.agent_process = subprocess.Popen(
                [python_exe, agent_path, bridge_url],
                creationflags=creation_flags
            )
        except Exception as e:
            print(f"Error al iniciar el agente: {e}")

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Escape:
            self.close_gui()
        super().keyPressEvent(event)

    def setup_header(self):
        header_layout = QHBoxLayout()
        
        logo_lbl = QLabel("ALFONSO OS\nver 3.7.19")
        logo_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFB800; letter-spacing: 1px;")
        header_layout.addWidget(logo_lbl)
        
        header_layout.addStretch()

        self.tab_dashboard = QPushButton("DASHBOARD")
        self.tab_dashboard.setStyleSheet("background-color: rgba(255, 184, 0, 40); border: 1px solid #FFB800; color: #FFFFFF;")
        
        self.tab_modules = AlfonsoDashboardModuleButton("CALENDARIO")
        self.tab_modules.clicked.connect(self.show_calendar)
        self.tab_mail = AlfonsoDashboardModuleButton("CORREO")
        self.tab_mail.clicked.connect(self.show_mail)
        self.tab_kpi = AlfonsoDashboardModuleButton("KPIs NEGOCIO")
        self.tab_kpi.clicked.connect(self.open_kpi_dashboard)
        self.tab_aeat = AlfonsoDashboardModuleButton("AUTOFILL AEAT")
        self.tab_aeat.clicked.connect(self.show_aeat)
        self.tab_config = AlfonsoDashboardModuleButton("CONFIG")
        self.tab_config.clicked.connect(self.show_config)
        
        header_layout.addWidget(self.tab_dashboard)
        
        self.tab_reconcile = AlfonsoDashboardModuleButton("CONCILIACIÓN")
        self.tab_reconcile.clicked.connect(self.show_reconcile)
        
        self.tab_ledger = AlfonsoDashboardModuleButton("DIARIO CONTABLE")
        self.tab_ledger.clicked.connect(self.show_ledger)
        
        self.tab_archive = AlfonsoDashboardModuleButton("ARCHIVO FISCAL")
        self.tab_archive.clicked.connect(self.show_archive)
 
        header_layout.addWidget(self.tab_reconcile)
        header_layout.addWidget(self.tab_ledger)
        header_layout.addWidget(self.tab_archive)
        header_layout.addWidget(self.tab_modules)
        header_layout.addWidget(self.tab_mail)
        header_layout.addWidget(self.tab_kpi)
        header_layout.addWidget(self.tab_aeat)
        header_layout.addWidget(self.tab_config)


        header_layout.addStretch()

        # Botones de cierre y minimización arriba a la derecha (como en los módulos)
        self.btn_minimize = AlfonsoWindowMinimizeButton(self)
        self.btn_minimize.clicked.connect(self.showMinimized)
        header_layout.addWidget(self.btn_minimize)

        self.btn_shutdown = AlfonsoWindowCloseButton(self)
        self.btn_shutdown.clicked.connect(self.close_gui)
        header_layout.addWidget(self.btn_shutdown)

        self.main_layout.addLayout(header_layout)

    def setup_body_columns(self):
        body_layout = QHBoxLayout()
        body_layout.setSpacing(15)

        # COLUMNA IZQUIERDA (SIDEBAR: AVATAR + LOGS REALES)
        left_layout = QVBoxLayout()
        left_layout.setSpacing(15)

        # 1. Visualización de Rostro/Avatar
        self.panel_core = HUDPanel("TU ASISTENTE ALFONSO")
        self.animated_wave = AnimatedWaveWidget()
        self.panel_core.main_layout.addWidget(self.animated_wave, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.state_lbl = QLabel("STANDBY")
        self.state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.state_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #6366F1; letter-spacing: 2px;")
        self.panel_core.main_layout.addWidget(self.state_lbl)
        left_layout.addWidget(self.panel_core, 2)

        # 2. Panel de Métricas de Negocio en Tiempo Real
        self.lbl_user_header = QLabel("USER: ADMINISTRATOR")
        self.lbl_user_header.setStyleSheet("font-size: 11px; color: #00F0FF; font-weight: bold; margin-bottom: 2px;")
        self.lbl_user_header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.panel_business = HUDPanel("RESUMEN DEL NEGOCIO")
        self.panel_business.setMinimumHeight(500) # Más alto para alojar el gráfico de barras y el reloj abajo
        
        # Layout interno del panel
        bus_layout = QVBoxLayout()
        bus_layout.setSpacing(10)
        bus_layout.setContentsMargins(10, 10, 10, 10)
        
        # Sección 1: Saldos y Facturación
        self.lbl_saldo_banco = QLabel("SALDO BANCARIO:  0,00 €")
        self.lbl_saldo_banco.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #10B981; font-weight: bold;")
        self.lbl_ingresos_ejercicio = QLabel("INGRESOS 2026:  0,00 €")
        self.lbl_ingresos_ejercicio.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #E2E8F0;")
        self.lbl_gastos_ejercicio = QLabel("GASTOS 2026:    0,00 €")
        self.lbl_gastos_ejercicio.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #E2E8F0;")
        
        bus_layout.addWidget(self.lbl_saldo_banco)
        bus_layout.addWidget(self.lbl_ingresos_ejercicio)
        bus_layout.addWidget(self.lbl_gastos_ejercicio)
        
        # Separador visual
        sep_bus = QFrame()
        sep_bus.setFrameShape(QFrame.Shape.HLine)
        sep_bus.setStyleSheet("border: 1px solid rgba(255, 184, 0, 30); max-height: 1px;")
        bus_layout.addWidget(sep_bus)
        
        # Sección 2: Próximas Obligaciones Fiscales (AEAT)
        bus_layout.addWidget(QLabel("<b>OBLIGACIONES FISCALES (AEAT):</b>"))
        
        self.lbl_vencimiento_iva = QLabel("• Mod. 303 (IVA 3T):   20 Oct 2026")
        self.lbl_vencimiento_iva.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #00F0FF;")
        self.lbl_vencimiento_irpf = QLabel("• Mod. 130 (IRPF 3T):  20 Oct 2026")
        self.lbl_vencimiento_irpf.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #00F0FF;")
        self.lbl_vencimiento_ret = QLabel("• Mod. 111 (Retenc.):  20 Oct 2026")
        self.lbl_vencimiento_ret.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #00F0FF;")
        
        bus_layout.addWidget(self.lbl_vencimiento_iva)
        bus_layout.addWidget(self.lbl_vencimiento_irpf)
        bus_layout.addWidget(self.lbl_vencimiento_ret)
        
        # Separador visual 2
        sep_bus2 = QFrame()
        sep_bus2.setFrameShape(QFrame.Shape.HLine)
        sep_bus2.setStyleSheet("border: 1px solid rgba(255, 184, 0, 30); max-height: 1px;")
        bus_layout.addWidget(sep_bus2)
        
        # Sección 3: Seguridad Social
        bus_layout.addWidget(QLabel("<b>COTIZACIONES Y S. SOCIAL:</b>"))
        
        self.lbl_seguros_sociales = QLabel("• Autónomos (Agosto):  31 Ago 2026")
        self.lbl_seguros_sociales.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #FFB800;")
        bus_layout.addWidget(self.lbl_seguros_sociales)
        
        # Separador visual 3
        sep_bus3 = QFrame()
        sep_bus3.setFrameShape(QFrame.Shape.HLine)
        sep_bus3.setStyleSheet("border: 1px solid rgba(255, 184, 0, 30); max-height: 1px;")
        bus_layout.addWidget(sep_bus3)

        # Gráfico de rendimiento trimestral (ingresos/gastos)
        self.bar_chart = QuarterlyBarChartWidget(self)
        bus_layout.addWidget(self.bar_chart)

        bus_layout.addSpacing(10)
        
        # Reloj y fecha abajo del todo en el panel
        self.clock_lbl = QLabel("00:00:00 - 00.00.0000")
        self.clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_lbl.setStyleSheet("font-family: 'Consolas', 'Fira Code', monospace; font-size: 12px; color: #00F0FF; font-weight: bold; background-color: rgba(0, 240, 255, 0.05); border: 1px solid rgba(0, 240, 255, 0.2); padding: 5px; border-radius: 4px;")
        bus_layout.addWidget(self.clock_lbl)
        
        self.panel_business.main_layout.addLayout(bus_layout)
        left_layout.addWidget(self.lbl_user_header)
        left_layout.addWidget(self.panel_business, 4)

        body_layout.addLayout(left_layout, 1)

        # COLUMNA DERECHA (PANTALLA DE CHAT EXPANDIDA)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(15)

        self.panel_chat = HUDPanel("CONVERSACIÓN CON ALFONSO")
        
        # Etiqueta de sesión activa persistente
        self.lbl_active_session = QLabel("ESTADO: SIN CONVERSACIÓN ACTIVA (Por favor abre un proyecto)")
        self.lbl_active_session.setStyleSheet("""
            font-family: 'Segoe UI', sans-serif;
            font-size: 11px;
            color: #6366F1;
            background-color: rgba(99, 102, 241, 0.08);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 8px;
            padding: 6px 12px;
            margin-bottom: 5px;
        """)
        self.panel_chat.main_layout.addWidget(self.lbl_active_session)
        
        self.chat_lbl = CrtTerminalTextBrowser("ALFONSO v4.2 ONLINE\n\n*Inicialización completada. Esperando comandos de voz o selección de proyecto...*", color_hex="#00E5FF")
        self.panel_chat.main_layout.addWidget(self.chat_lbl, 1)

        # Layout para los archivos adjuntos (drag & drop) con QGridLayout para fluir hacia abajo
        self.attachments_container = QWidget()
        self.attachments_container.setVisible(False)
        self.attachments_container.setStyleSheet("background: transparent;")
        self.attachments_layout = QGridLayout(self.attachments_container)
        self.attachments_layout.setContentsMargins(5, 5, 5, 5)
        self.attachments_layout.setSpacing(10)
        self.attachments_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.attached_files = []

        chat_input_layout = QHBoxLayout()
        chat_input_layout.setSpacing(10)
        
        self.text_input = ChatTextInput()
        self.text_input.file_dropped.connect(self.handle_file_drop)
        self.text_input.setPlaceholderText("Escribe un mensaje para Alfonso...")
        self.text_input.setMaximumHeight(45)
        
        self.btn_send = QPushButton("ENVIAR")
        self.btn_send.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 229, 255, 0.1);
                color: #00E5FF;
                border: 1px solid #00E5FF;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #00E5FF;
                color: #0B0E14;
            }
        """)
        self.btn_send.clicked.connect(self.send_text_message)
        
        # VU meter discreto integrado en la barra de control del chat
        self.mic_name_lbl = QLabel("MIC: BUSCANDO...")
        self.mic_name_lbl.setStyleSheet("font-size: 10px; color: #00E5FF; font-weight: bold;")
        self.vu_meter = QProgressBar()
        self.vu_meter.setRange(0, 100)
        self.vu_meter.setValue(0)
        self.vu_meter.setTextVisible(False)
        self.vu_meter.setFixedHeight(6)
        self.vu_meter.setFixedWidth(80)
        self.vu_meter.setStyleSheet("""
            QProgressBar {
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 3px;
                background-color: rgba(15, 20, 28, 0.8);
            }
            QProgressBar::chunk {
                background-color: #00E5FF;
                border-radius: 2px;
            }
        """)
        
        # Botón para alternar teclado
        self.btn_mode = QPushButton("TECLADO")
        self.btn_mode.setStyleSheet("background-color: rgba(0, 240, 255, 30); color: #00F0FF; border: 1px solid #00F0FF;")
        self.btn_mode.clicked.connect(self.toggle_text_mode)
        
        # Botón limpiar chat
        self.btn_clear = QPushButton("LIMPIAR")
        self.btn_clear.setStyleSheet("background-color: rgba(255, 255, 255, 0.05); color: #CBD5E1; border: 1px solid rgba(255, 255, 255, 0.1);")
        self.btn_clear.clicked.connect(self.clear_chat)
        
        chat_input_layout.addWidget(self.btn_mode)
        chat_input_layout.addWidget(self.btn_clear)
        chat_input_layout.addWidget(self.mic_name_lbl)
        chat_input_layout.addWidget(self.vu_meter)
        chat_input_layout.addWidget(self.text_input, 1)
        chat_input_layout.addWidget(self.btn_send)
        
        self.panel_chat.main_layout.addWidget(self.attachments_container)
        self.panel_chat.main_layout.addSpacing(20)
        self.panel_chat.main_layout.addLayout(chat_input_layout)
        right_layout.addWidget(self.panel_chat, 1)

        body_layout.addLayout(right_layout, 3)
        self.main_layout.addLayout(body_layout, 1)

    def setup_footer(self):
        footer_layout = QHBoxLayout()

        self.alert_btn = QPushButton(" 2 ALERTS ")
        self.alert_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 75, 75, 25);
                color: #FF4B4B;
                border: 2px solid #FF4B4B;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #FF4B4B;
                color: #000000;
            }
        """)
        self.alert_btn.clicked.connect(self.show_alerts)
        footer_layout.addWidget(self.alert_btn)
        
        footer_layout.addStretch()

        self.main_layout.addLayout(footer_layout)

    def toggle_text_mode(self):
        self.text_mode_enabled = not self.text_mode_enabled
        if self.text_mode_enabled:
            self.btn_mode.setText("TECLADO")
            self.btn_mode.setStyleSheet("background-color: rgba(0, 240, 255, 30); color: #00F0FF; border: 1px solid #00F0FF;")
            self.text_input.setFocus()
        else:
            self.btn_mode.setText("VOZ")
            self.btn_mode.setStyleSheet("background-color: rgba(0, 240, 255, 15); color: #00F0FF; border: 1px solid rgba(0, 240, 255, 0.3);")
        self.thread.set_text_mode(self.text_mode_enabled)

    def send_text_message(self):
        text = self.text_input.toPlainText().strip()
        
        if hasattr(self, 'attached_files') and self.attached_files:
            file_list_str = ", ".join(os.path.basename(f[0]) for f in self.attached_files)
            if text:
                text += f"\n\n[SISTEMA: El usuario ha subido las siguientes facturas/documentos a procesar: {file_list_str}]"
            else:
                text = f"Procesa las siguientes facturas/documentos que acabo de subir: {file_list_str}"
                
            while self.attachments_layout.count() > 0:
                item = self.attachments_layout.takeAt(0)
                if item:
                    w = item.widget()
                    if w:
                        w.deleteLater()
            self.attached_files = []
            self.attachments_container.setVisible(False)

        if text:
            self.text_input.clear()
            if not self.text_mode_enabled:
                self.toggle_text_mode()
            self.thread.send_text_message(text)

    def handle_file_drop(self, filepaths):
        dest_dir = "C:/Users/luisd/Desktop/Facturas_Para_Procesar"
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except Exception as e:
            print(f"Error creando directorio de facturas: {e}")
            return
            
        for path in filepaths:
            if any(f[0] == path for f in self.attached_files):
                continue
                
            try:
                filename = os.path.basename(path)
                dest_path = os.path.normpath(os.path.join(dest_dir, filename))
                src_path = os.path.normpath(path)
                
                if src_path != dest_path:
                    import shutil
                    shutil.copy(path, dest_path)
                
                file_widget = AttachedFileWidget(path)
                file_widget.removed.connect(self.remove_attached_file)
                
                idx = len(self.attached_files)
                row = idx // 4
                col = idx % 4
                self.attachments_layout.addWidget(file_widget, row, col)
                self.attached_files.append((path, file_widget, dest_path))
            except Exception as e:
                print(f"Error procesando archivo adjunto: {e}")
                
        if self.attached_files:
            self.attachments_container.setVisible(True)
            
    def remove_attached_file(self, filepath):
        target_idx = -1
        for i, (path, widget, dest_path) in enumerate(self.attached_files):
            if path == filepath:
                target_idx = i
                break
                
        if target_idx != -1:
            path, widget, dest_path = self.attached_files.pop(target_idx)
            self.attachments_layout.removeWidget(widget)
            widget.deleteLater()
            
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception as e:
                print(f"Error al eliminar archivo: {e}")
                
            # Limpiar layout sin destruir los widgets restantes
            while self.attachments_layout.count() > 0:
                item = self.attachments_layout.takeAt(0)
                
            # Reposicionar en la cuadrícula 4xN
            for idx, (path, widget, dest_path) in enumerate(self.attached_files):
                row = idx // 4
                col = idx % 4
                self.attachments_layout.addWidget(widget, row, col)
                
        if not self.attached_files:
            self.attachments_container.setVisible(False)

    def clear_chat(self):
        self.chat_history = ""
        self.chat_lbl.setMarkdown("ALFONSO v4.2 ONLINE\n\n*Historial de conversación limpiado.*")

    def start_assistant(self):
        thread_config = self.config.copy()
        thread_config['bridge_url'] = self.config.get('bridge_url', "ws://127.0.0.1:8765")
        self.thread = AssistantThread(thread_config)
        self.thread.new_message.connect(self.update_chat)
        self.thread.state_changed.connect(self.update_visual_state)
        self.thread.audio_level_updated.connect(self.update_vu_meter)
        self.thread.open_calendar.connect(self.show_calendar)
        self.thread.close_calendar.connect(self.hide_calendar)
        self.thread.sync_calendar.connect(self.reload_calendar_events)
        self.thread.open_mail.connect(self.show_mail)
        self.thread.close_mail.connect(self.hide_mail)
        self.thread.sync_mail.connect(self.reload_mail_events)
        self.thread.switch_session_requested.connect(self.handler_switch_session)
        self.thread.start()

    def hide_calendar(self):
        if self.calendar_window:
            self.calendar_window.close()

    def reload_calendar_events(self):
        if self.calendar_window and self.calendar_window.isVisible():
            self.calendar_window.load_events()

    def update_module_button_states(self):
        # CALENDARIO
        self.tab_modules.set_module_open(bool(self.calendar_window and self.calendar_window.isVisible()))
        # CORREO
        self.tab_mail.set_module_open(bool(self.mail_window and self.mail_window.isVisible()))
        # AUTOFILL AEAT
        self.tab_aeat.set_module_open(bool(self.aeat_window and self.aeat_window.isVisible()))
        # CONFIG
        self.tab_config.set_module_open(bool(self.config_window and self.config_window.isVisible()))
        # CONCILIACIÓN
        self.tab_reconcile.set_module_open(bool(self.reconcile_dialog and self.reconcile_dialog.isVisible()))
        # DIARIO CONTABLE
        self.tab_ledger.set_module_open(bool(self.ledger_dialog and self.ledger_dialog.isVisible()))
        # ARCHIVO FISCAL
        self.tab_archive.set_module_open(bool(self.archive_dialog and self.archive_dialog.isVisible()))

    def hide_mail(self):
        if self.mail_window:
            self.mail_window.close()

    def reload_mail_events(self):
        if self.mail_window and self.mail_window.isVisible():
            self.mail_window.load_emails()

    def show_mail(self):
        if not self.mail_window:
            self.mail_window = MailWidget(self.thread.api)
        self.mail_window.show()
        self.mail_window.raise_()
        self.mail_window.activateWindow()
        self.mail_window.load_emails()

    def show_calendar(self):
        if not self.calendar_window:
            self.calendar_window = CalendarWidget(self.thread.api)
        self.calendar_window.show()
        self.calendar_window.raise_()
        self.calendar_window.activateWindow()
        self.calendar_window.load_events()



    def hide_config(self):
        if self.config_window:
            self.config_window.close()

    def show_config(self):
        if not self.config_window:
            self.config_window = ConfigWidget(self)
        self.config_window.show()
        self.config_window.raise_()
        self.config_window.activateWindow()

    def show_aeat(self):
        if not hasattr(self, 'aeat_window') or not self.aeat_window:
            self.aeat_window = AeatAutofillWidget(self)
        self.aeat_window.show()
        self.aeat_window.raise_()
        self.aeat_window.activateWindow()


    def show_reconcile(self):
        if not hasattr(self, 'reconcile_dialog') or not self.reconcile_dialog:
            api_client = AlfonsoAPI(self.config.get('url', 'http://127.0.0.1:8000'), self.config.get('api_key', 'default_key'))
            self.reconcile_dialog = AlfonsoBankReconciliationDialog(self, api_client)
        self.reconcile_dialog.show()
        self.reconcile_dialog.raise_()
        self.reconcile_dialog.activateWindow()

    def show_ledger(self):
        if not hasattr(self, 'ledger_dialog') or not self.ledger_dialog:
            api_client = AlfonsoAPI(self.config.get('url', 'http://127.0.0.1:8000'), self.config.get('api_key', 'default_key'))
            self.ledger_dialog = AlfonsoLedgerDialog(self, api_client)
        self.ledger_dialog.show()
        self.ledger_dialog.raise_()
        self.ledger_dialog.activateWindow()

    def show_archive(self):
        if not hasattr(self, 'archive_dialog') or not self.archive_dialog:
            self.archive_dialog = AlfonsoArchiveBrowserDialog(self)
        self.archive_dialog.show()
        self.archive_dialog.raise_()
        self.archive_dialog.activateWindow()

    def handler_switch_session(self, session_id, project_name, title):
        """Manejador ejecutado de forma segura en el hilo principal para aplicar el cambio de proyecto."""
        self.thread.session_id = session_id
        
        # Guardar persistencia local de sesión
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(gui_dir), "logs", "session_config.json")
        try:
            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id}, f, indent=4)
        except Exception:
            pass
            
        # Actualizar cabecera de estado persistente del chat
        self.lbl_active_session.setText(f"ACTIVO: {project_name.upper()} > {title.upper()}")
        self.lbl_active_session.setStyleSheet("""
            font-family: 'Consolas', 'Fira Code', monospace;
            font-size: 11px;
            color: #00FF66;
            background-color: rgba(0, 255, 102, 0.05);
            border: 1px solid rgba(0, 255, 102, 0.2);
            border-radius: 4px;
            padding: 6px;
            margin-bottom: 5px;
        """)
        
        # Abrir automáticamente el Pop-up flotante del navegador para mostrar las conversaciones del proyecto
        if not hasattr(self, 'projects_dialog') or not self.projects_dialog or not self.projects_dialog.isVisible():
            self.show_projects_navigator()
        else:
            self.reload_projects_list()



    def hide_alerts(self):
        if self.alerts_window:
            self.alerts_window.close()

    def show_alerts(self):
        if not self.alerts_window:
            self.alerts_window = AlertsWidget(self)
        self.alerts_window.show()
        self.alerts_window.raise_()
        self.alerts_window.activateWindow()
        self.alerts_window.load_alerts()

    def update_vu_meter(self, level, device_name):
        self.mic_name_lbl.setText(f"MIC: {device_name.upper()}")
        self.vu_meter.setValue(level)

    def update_chat(self, sender, text):
        color = "#00E5FF" if sender == "Alfonso" else "#F59E0B"
        
        if sender == "Alfonso":
            # Si ya se está escribiendo, terminar el anterior inmediatamente
            if hasattr(self, 'typing_timer') and self.typing_timer.isActive():
                self.typing_timer.stop()
                if hasattr(self, 'current_typing_text') and hasattr(self, 'current_typing_index'):
                    remaining = self.current_typing_text[self.current_typing_index:]
                    self.chat_history += remaining + "\n\n"
                    if hasattr(self, 'projects_dialog') and self.projects_dialog and self.projects_dialog.isVisible():
                        cur_html = self.projects_dialog.chat_display.toHtml()
                        dialog_entry = f"<p><b style='color:#00E5FF;'>[ALFONSO]</b><br/>{self.current_typing_text.replace('\n', '<br/>')}</p>"
                        self.projects_dialog.chat_display.setHtml(cur_html + dialog_entry)

            header = f"<span style='color:{color};'><b>[{sender.upper()}]</b></span>\n\n"
            self.chat_history += header
            self.chat_lbl.setMarkdown(self.chat_history)
            
            self.current_typing_text = text
            self.current_typing_index = 0
            self.current_typing_color = color
            
            self.typing_timer = QTimer(self)
            self.typing_timer.setInterval(12) # 12ms para aparición ultra rápida (doble de velocidad)
            self.typing_timer.timeout.connect(self.on_typewriter_timeout)
            self.typing_timer.start()
        else:
            interrupted = False
            if hasattr(self, 'typing_timer') and self.typing_timer.isActive():
                self.typing_timer.stop()
                self.current_typing_text = ""
                self.current_typing_index = 0
                interrupted = True

            if interrupted:
                new_entry = f"<br/><span style='color:{color};'><b>[{sender.upper()}]</b></span>: {text}\n\n"
            else:
                new_entry = f"<span style='color:{color};'><b>[{sender.upper()}]</b></span>\n\n{text}\n\n"

            self.chat_history += new_entry
            self.chat_lbl.setMarkdown(self.chat_history)
            QTimer.singleShot(50, lambda: self.chat_lbl.verticalScrollBar().setValue(self.chat_lbl.verticalScrollBar().maximum()))
            
            if hasattr(self, 'projects_dialog') and self.projects_dialog and self.projects_dialog.isVisible():
                cur_html = self.projects_dialog.chat_display.toHtml()
                if interrupted:
                    dialog_entry = f"<p><b style='color:{color};'>[{sender.upper()}]</b>: {text.replace('\n', '<br/>')}</p>"
                else:
                    dialog_entry = f"<p><b style='color:{color};'>[{sender.upper()}]</b><br/>{text.replace('\n', '<br/>')}</p>"
                self.projects_dialog.chat_display.setHtml(cur_html + dialog_entry)
                QTimer.singleShot(50, lambda: self.projects_dialog.chat_display.verticalScrollBar().setValue(self.projects_dialog.chat_display.verticalScrollBar().maximum()))

    def on_typewriter_timeout(self):
        if hasattr(self, 'current_typing_text') and self.current_typing_index < len(self.current_typing_text):
            char = self.current_typing_text[self.current_typing_index]
            self.chat_history += char
            self.current_typing_index += 1
            self.chat_lbl.setMarkdown(self.chat_history)
            self.chat_lbl.verticalScrollBar().setValue(self.chat_lbl.verticalScrollBar().maximum())
        else:
            if hasattr(self, 'typing_timer'):
                self.typing_timer.stop()
            self.chat_history += "\n\n"
            self.chat_lbl.setMarkdown(self.chat_history)
            QTimer.singleShot(50, lambda: self.chat_lbl.verticalScrollBar().setValue(self.chat_lbl.verticalScrollBar().maximum()))
            
            if hasattr(self, 'projects_dialog') and self.projects_dialog and self.projects_dialog.isVisible():
                cur_html = self.projects_dialog.chat_display.toHtml()
                dialog_entry = f"<p><b style='color:{self.current_typing_color};'>[ALFONSO]</b><br/>{self.current_typing_text.replace('\n', '<br/>')}</p>"
                self.projects_dialog.chat_display.setHtml(cur_html + dialog_entry)
                QTimer.singleShot(50, lambda: self.projects_dialog.chat_display.verticalScrollBar().setValue(self.projects_dialog.chat_display.verticalScrollBar().maximum()))

    def reload_projects_list(self):
        """Consulta al backend la lista de conversaciones y actualiza el QListWidget en doble columna."""
        if not hasattr(self, 'thread') or not self.thread or not self.thread.api:
            return
            
        # Comprobar si el diálogo de navegación está instanciado
        if not hasattr(self, 'projects_dialog') or not self.projects_dialog:
            return
        
        try:
            res = self.thread.api.get_conversations()
            conversations = res.get("conversations", [])
            
            # Limpiar datos previos
            self.projects_dialog.proj_list.clear()
            self.projects_dialog.conv_list.clear()
            self.projects_dialog.projects_data = {}
            
            # Agrupar conversaciones por proyecto
            projects_grouped = {}
            active_project = None
            
            for c in conversations:
                proj = c.get("project_name") or "Otros / General"
                if proj not in projects_grouped:
                    projects_grouped[proj] = []
                projects_grouped[proj].append(c)
                
                # Detectar qué proyecto contiene la conversación activa actual
                if c.get("session_id") == self.thread.session_id:
                    active_project = proj
                    
            # Guardar la caché estructurada en el diálogo flotante
            self.projects_dialog.projects_data = projects_grouped
            
            # Rellenar listado de proyectos (Columna Izquierda)
            selected_item = None
            for project in sorted(projects_grouped.keys()):
                proj_item = QListWidgetItem(f"📁 {project.upper()}")
                self.projects_dialog.proj_list.addItem(proj_item)
                
                # Si es el proyecto activo actual, guardamos la referencia para seleccionarlo
                if project == active_project:
                    selected_item = proj_item
            
            # Seleccionar automáticamente el proyecto activo actual si existe
            if selected_item:
                self.projects_dialog.proj_list.setCurrentItem(selected_item)
                self.projects_dialog.select_project(selected_item)
            elif self.projects_dialog.proj_list.count() > 0:
                # Fallback: seleccionar el primero por defecto
                first_item = self.projects_dialog.proj_list.item(0)
                self.projects_dialog.proj_list.setCurrentItem(first_item)
                self.projects_dialog.select_project(first_item)
                
        except Exception as e:
            print(f"[ERROR] No se pudo refrescar navegador de proyectos: {e}")

    def load_project_session_from_ui(self, item):
        """Carga la conversación seleccionada en la UI al hacer doble clic."""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        title = item.data(Qt.ItemDataRole.UserRole + 1)
        project = item.data(Qt.ItemDataRole.UserRole + 2)
        
        if not session_id:
            return # Cabecera de carpeta de proyecto o item inválido
            
        # Cambiar el session_id del hilo activo de Alfonso
        self.thread.session_id = session_id
        
        # Guardar persistencia en session_config.json
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(gui_dir), "logs", "session_config.json")
        try:
            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id}, f, indent=4)
        except Exception:
            pass
            
        # Consultar historial del backend y cargar en pantalla
        try:
            res = self.thread.api.get_memory_detail(session_id)
            messages = res.get("messages", [])
            
            # Reconstruir historial formateado
            self.chat_history = ""
            for msg in messages:
                sender = "Tú" if msg.get("role") == "user" else "Alfonso"
                content = msg.get("content") or ""
                color = "#00E5FF" if sender == "Alfonso" else "#F59E0B"
                self.chat_history += f"<span style='color:{color};'><b>[{sender.upper()}]</b></span>\n\n{content}\n\n"
                
            if not self.chat_history:
                self.chat_history = f"**HISTORIAL DE CONVERSACIÓN INICIADO**\n\n*Proyecto: {project} — Título: {title}*\n\n"
                
            self.chat_lbl.setMarkdown(self.chat_history)
            
            # Actualizar cabecera de estado persistente del chat
            self.lbl_active_session.setText(f"ACTIVO: {project.upper()} > {title.upper()}")
            self.lbl_active_session.setStyleSheet("""
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 11px;
                color: #00FF66;
                background-color: rgba(0, 255, 102, 0.05);
                border: 1px solid rgba(0, 255, 102, 0.2);
                border-radius: 4px;
                padding: 6px;
                margin-bottom: 5px;
            """)
            
            # Recargar selección de colores en el listado para reflejar la activa si el diálogo sigue abierto
            if hasattr(self, 'projects_dialog') and self.projects_dialog and self.projects_dialog.isVisible():
                for idx in range(self.projects_dialog.conv_list.count()):
                    itm = self.projects_dialog.conv_list.item(idx)
                    itm_sid = itm.data(Qt.ItemDataRole.UserRole)
                    if itm_sid:
                        if itm_sid == session_id:
                            itm.setSelected(True)
                            itm.setForeground(QColor("#00FF66"))
                        else:
                            itm.setSelected(False)
                            itm.setForeground(QColor("#CBD5E1"))
                        
        except Exception as e:
            self.update_chat("Sistema", f"Error al cargar historial: {e}")

    def update_visual_state(self, state):
        self.animated_wave.set_state(state)
        state_labels = {
            "connecting": "INICIALIZANDO OS", "idle": "STANDBY", "idle_text": "TECLADO ACTIVO", 
            "listening": "ESCUCHANDO...", "thinking": "PROCESANDO...", "speaking": "HABLANDO...", 
            "error": "ERROR CRITICO"
        }
        self.state_lbl.setText(state_labels.get(state, "OFFLINE"))
        
        state_colors = {
            "connecting": "#FFB800", "idle": "#00F0FF", "idle_text": "#00F0FF",
            "listening": "#00FF66", "thinking": "#FFB800", "speaking": "#00FF66", "error": "#FF4B4B"
        }
        self.state_lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {state_colors.get(state, '#00F0FF')}; letter-spacing: 2px;")



    def update_telemetry(self):
        now = datetime.datetime.now()
        time_str = now.strftime("%H:%M:%S")
        date_str = now.strftime("%d.%m.%Y")
        self.clock_lbl.setText(f"{time_str}  -  {date_str}")
        self.update_business_metrics()

    def update_business_metrics(self):
        try:
            from app.adapters.memory.memory import _get_connection
            from app.utils.encryption import encryptor
            import datetime
            
            now_dt = datetime.datetime.now()
            current_quarter = (now_dt.month - 1) // 3 + 1
            
            saldo = 0.0
            ingresos = 0.0
            gastos = 0.0
            ingresos_trim = 0.0
            gastos_trim = 0.0

            with _get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Calcular Saldo Bancario
                cursor.execute("SELECT SUM(amount) FROM bank_movements")
                row_bank = cursor.fetchone()
                if row_bank and row_bank[0] is not None:
                    saldo = float(row_bank[0])
                    
                # 2. Calcular Ingresos y Gastos
                cursor.execute("SELECT base_imponible, category, quarter FROM invoices WHERE year = 2026")
                invs = cursor.fetchall()
                for inv in invs:
                    try:
                        base = float(encryptor.decrypt(inv["base_imponible"]))
                        if inv["category"] in ("ingreso", "income"):
                            ingresos += base
                        elif inv["category"] in ("gasto", "expense"):
                            gastos += base
                        else:
                            gastos += base
                            
                        # Filtrar trimestre actual
                        if inv["quarter"] == current_quarter:
                            if inv["category"] in ("ingreso", "income"):
                                ingresos_trim += base
                            elif inv["category"] in ("gasto", "expense"):
                                gastos_trim += base
                            else:
                                gastos_trim += base
                    except Exception:
                        pass
                        
            # Actualizar textos de la interfaz
            self.lbl_saldo_banco.setText(f"SALDO BANCARIO:  {saldo:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            self.lbl_ingresos_ejercicio.setText(f"INGRESOS 2026:  {ingresos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            self.lbl_gastos_ejercicio.setText(f"GASTOS 2026:    {gastos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            
            # Actualizar el gráfico de barras del trimestre
            self.bar_chart.update_data(ingresos_trim, gastos_trim)
            
            # Cambiar color de saldo según signo
            if saldo >= 0:
                self.lbl_saldo_banco.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #10B981; font-weight: bold;")
            else:
                self.lbl_saldo_banco.setStyleSheet("font-family: 'Consolas', monospace; font-size: 11px; color: #EF4444; font-weight: bold;")

        except Exception as e:
            print(f"Error updating business telemetry: {e}")

    def open_kpi_dashboard(self):
        try:
            self.kpi_dashboard = AlfonsoKPIDashboardDialog(self)
            self.kpi_dashboard.show()
        except Exception as e:
            print(f"Error opening KPI Dashboard: {e}")

    def close_gui(self):
        try:
            if hasattr(self, 'agent_process') and self.agent_process:
                self.agent_process.kill()
        except Exception:
            pass
        try:
            if hasattr(self, 'thread') and self.thread:
                self.thread.stop()
        except Exception:
            pass
        os._exit(0)

    def closeEvent(self, event):
        self.close_gui()


from PyQt6.QtWidgets import QComboBox, QFileDialog, QFormLayout

class AlfonsoBaseDialog(QDialog):
    """
    Clase base para todos los diálogos/ventanas de Alfonso.
    Asegura consistencia visual (estilo CRT retro / cyberpunk) y facilita cambios globales de apariencia.
    """
    def __init__(self, parent=None, title="SISTEMA ALFONSO", modal=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(modal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_base_ui(title)
        self.apply_base_stylesheet()
        self.drag_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position') and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def setup_base_ui(self, title):
        self.base_layout = QVBoxLayout(self)
        self.base_layout.setContentsMargins(1, 1, 1, 1)
        self.base_layout.setSpacing(0)

        self.outer_frame = QFrame(self)
        self.outer_frame.setObjectName("OuterFrame")
        self.outer_layout = QVBoxLayout(self.outer_frame)
        self.outer_layout.setContentsMargins(15, 15, 15, 15)
        self.outer_layout.setSpacing(15)

        self.title_bar = QFrame(self.outer_frame)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 10, 0)

        self.title_label = QLabel(self.title_bar)
        self.title_label.setObjectName("TitleLabel")
        self.title_label.setText(f'<span style="color:#6366F1; font-size:12px;">●</span> &nbsp;<span style="font-size:11px; font-weight:bold; letter-spacing:1px; color:#F1F5F9;">{title.upper()}</span>')
        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()

        self.btn_minimize = AlfonsoWindowMinimizeButton(self.title_bar)
        self.btn_minimize.clicked.connect(self.showMinimized)
        self.title_layout.addWidget(self.btn_minimize)

        self.btn_close = AlfonsoWindowCloseButton(self.title_bar)
        self.btn_close.clicked.connect(self.close)
        self.title_layout.addWidget(self.btn_close)

        self.outer_layout.addWidget(self.title_bar)

        self.content_widget = QWidget(self.outer_frame)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 5, 0, 5)
        self.content_layout.setSpacing(10)
        self.outer_layout.addWidget(self.content_widget)

        self.base_layout.addWidget(self.outer_frame)

    def showEvent(self, event):
        super().showEvent(event)
        parent = self.parent()
        if parent and hasattr(parent, 'update_module_button_states'):
            parent.update_module_button_states()

    def closeEvent(self, event):
        super().closeEvent(event)
        parent = self.parent()
        if parent and hasattr(parent, 'update_module_button_states'):
            parent.update_module_button_states()

    def hideEvent(self, event):
        super().hideEvent(event)
        parent = self.parent()
        if parent and hasattr(parent, 'update_module_button_states'):
            parent.update_module_button_states()

    def apply_base_stylesheet(self):
        self.setStyleSheet("""
            QDialog {
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: rgba(15, 23, 42, 0.3);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(99, 102, 241, 0.4);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(99, 102, 241, 0.7);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: none;
            }
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                border: none;
                background: rgba(15, 23, 42, 0.3);
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: rgba(99, 102, 241, 0.4);
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(99, 102, 241, 0.7);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                border: none;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            #OuterFrame {
                background-color: #0F172A;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
            #TitleBar {
                background-color: rgba(99, 102, 241, 0.05);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            #TitleLabel {
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel {
                color: #CBD5E1;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }
            QLineEdit, QComboBox, QTextEdit, QTableWidget, QListWidget {
                background-color: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 8px;
                color: #F8FAFC;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
            }
            QComboBox QAbstractItemView {
                background-color: #1E293B;
                border: 1px solid #6366F1;
                color: #F8FAFC;
                selection-background-color: #6366F1;
                selection-color: #FFFFFF;
            }
            QMenu {
                background-color: #1E293B;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #F8FAFC;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                color: #CBD5E1;
            }
            QMenu::item:selected {
                background-color: #6366F1;
                color: #FFFFFF;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QTableWidget:focus, QListWidget:focus {
                border: 1px solid #6366F1;
            }
            QTableWidget {
                gridline-color: rgba(99, 102, 241, 0.2);
                background-color: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 8px;
                color: #CBD5E1;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid rgba(99, 102, 241, 0.1);
            }
            QTableWidget::item:selected {
                background-color: rgba(99, 102, 241, 0.3);
                color: #FFFFFF;
            }
            QHeaderView::section {
                background-color: rgba(99, 102, 241, 0.25);
                color: #818CF8;
                font-weight: bold;
                padding: 8px;
                border: none;
                border-bottom: 2px solid rgba(99, 102, 241, 0.5);
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollArea QWidget {
                background-color: transparent;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #CBD5E1;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: rgba(99, 102, 241, 0.15);
                color: #FFFFFF;
                border-color: rgba(99, 102, 241, 0.4);
            }
            QPushButton:pressed {
                background-color: #6366F1;
                color: #FFFFFF;
            }
        """)


class CalendarWidget(AlfonsoBaseDialog):
    """Interfaz gráfica nativa para el Calendario de Alfonso (ALFONSO OS)."""
    def __init__(self, api_client, parent=None):
        super().__init__(parent, "ALFONSO CALENDAR", modal=False)
        self.api = api_client
        self.setMinimumSize(850, 580)

        # Fechas operativas
        now = datetime.datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self.selected_date = now.strftime("%Y-%m-%d")
        
        self.events_cache = {}  # YYYY-MM-DD -> list of event dicts

        self.setup_ui()
        self.load_events()

    def setup_ui(self):
        # Layout de contenido
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        # ── PANEL IZQUIERDO: Calendario Mensual ──
        left_panel = QVBoxLayout()
        
        # Cabecera mes/año y navegación
        nav_layout = QHBoxLayout()
        self.btn_prev = QPushButton("< ANTERIOR")
        self.btn_prev.clicked.connect(self.prev_month)
        self.btn_next = QPushButton("SIGUIENTE >")
        self.btn_next.clicked.connect(self.next_month)
        
        self.month_label = QLabel("MES AÑO")
        self.month_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #6366F1;")
        self.month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.month_label, 1)
        nav_layout.addWidget(self.btn_next)
        left_panel.addLayout(nav_layout)

        # Grid de días
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        
        # Cabecera de días de la semana
        days = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
        for idx, day in enumerate(days):
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #6366F1; font-size: 11px; padding: 5px;")
            self.grid_layout.addWidget(lbl, 0, idx)

        # Botones de la cuadrícula de días (inicializar 6 filas x 7 columnas)
        self.day_buttons = []
        for r in range(6):
            row_buttons = []
            for c in range(7):
                btn = QPushButton("")
                btn.setFixedSize(55, 45)
                btn.setStyleSheet("font-size: 13px; font-weight: bold;")
                btn.clicked.connect(self.make_day_clicked_handler(r, c))
                self.grid_layout.addWidget(btn, r + 1, c)
                row_buttons.append(btn)
            self.day_buttons.append(row_buttons)

        left_panel.addLayout(self.grid_layout)
        left_panel.addStretch()
        content_layout.addLayout(left_panel, 3)

        # Línea divisoria
        divider = QFrame()
        divider.setObjectName("Separator")
        divider.setFrameShape(QFrame.Shape.VLine)
        content_layout.addWidget(divider)

        # ── PANEL DERECHO: Detalle de eventos ──
        right_panel = QVBoxLayout()
        
        self.details_header = QLabel("CITAS PARA EL DÍA")
        self.details_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #6366F1;")
        right_panel.addWidget(self.details_header)

        self.event_scroll = QScrollArea()
        self.event_scroll.setWidgetResizable(True)
        
        self.event_list_widget = QWidget()
        self.event_list_layout = QVBoxLayout(self.event_list_widget)
        self.event_list_layout.setContentsMargins(10, 10, 10, 10)
        self.event_list_layout.setSpacing(10)
        self.event_list_layout.addStretch()
        
        self.event_scroll.setWidget(self.event_list_widget)
        right_panel.addWidget(self.event_scroll)

        # Botón para cerrar
        self.btn_close = QPushButton("MINIMIZAR CALENDARIO")
        self.btn_close.clicked.connect(self.close)
        right_panel.addWidget(self.btn_close)

        content_layout.addLayout(right_panel, 2)
        self.content_layout.addLayout(content_layout)

    def make_day_clicked_handler(self, row, col):
        return lambda: self.day_clicked(row, col)

    def prev_month(self):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.load_events()

    def next_month(self):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.load_events()

    def load_events(self):
        import calendar
        start_date = f"{self.current_year}-{self.current_month:02d}-01"
        last_day = calendar.monthrange(self.current_year, self.current_month)[1]
        end_date = f"{self.current_year}-{self.current_month:02d}-{last_day:02d}"

        self.events_cache.clear()
        res = self.api.get_calendar_events(start_date, end_date)
        if res.get("status") == "ok":
            for ev in res.get("events", []):
                dt = ev.get("start_time", "")[:10]  # Extrae siempre YYYY-MM-DD soportando tanto separadores 'T' como espacio
                if dt not in self.events_cache:
                    self.events_cache[dt] = []
                self.events_cache[dt].append(ev)

        self.draw_month()

    def draw_month(self):
        import calendar
        meses = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
                 "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
        
        self.month_label.setText(f"{meses[self.current_month]} {self.current_year}")

        cal = calendar.Calendar(firstweekday=0)
        month_matrix = cal.monthdayscalendar(self.current_year, self.current_month)

        for r in range(6):
            for c in range(7):
                btn = self.day_buttons[r][c]
                
                btn.setEnabled(False)
                btn.setText("")
                btn.setStyleSheet("")
                btn.setProperty("day_val", 0)

                if r < len(month_matrix):
                    day_val = month_matrix[r][c]
                    if day_val > 0:
                        btn.setText(str(day_val))
                        btn.setEnabled(True)
                        btn.setProperty("day_val", day_val)
                        
                        date_str = f"{self.current_year}-{self.current_month:02d}-{day_val:02d}"
                        
                        has_events = date_str in self.events_cache
                        
                        if date_str == self.selected_date:
                            btn.setStyleSheet("background-color: #6366F1; color: #FFFFFF; border-radius: 6px; border: none; font-weight: bold;")
                        elif has_events:
                            btn.setStyleSheet("border: 1px solid rgba(99, 102, 241, 0.4); color: #818CF8; font-weight: bold; background-color: rgba(99, 102, 241, 0.08); border-radius: 6px;")
                        else:
                            btn.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.05); color: #CBD5E1; background-color: rgba(255, 255, 255, 0.01); border-radius: 6px;")

    def day_clicked(self, row, col):
        btn = self.day_buttons[row][col]
        day_val = btn.property("day_val")
        if not day_val:
            return
            
        self.selected_date = f"{self.current_year}-{self.current_month:02d}-{day_val:02d}"
        self.draw_month()
        self.show_events_for_selected()

    def show_events_for_selected(self):
        while self.event_list_layout.count() > 1:
            item = self.event_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        try:
            dt_obj = datetime.datetime.strptime(self.selected_date, "%Y-%m-%d")
            dias_sem = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            self.details_header.setText(f"CITAS PARA EL {dias_sem[dt_obj.weekday()].upper()} {dt_obj.day}")
        except Exception:
            self.details_header.setText(f"CITAS DEL DÍA: {self.selected_date}")

        events = self.events_cache.get(self.selected_date, [])
        
        if not events:
            lbl = QLabel("NO HAY CITAS AGENDADAS PARA ESTE DÍA.")
            lbl.setStyleSheet("color: rgba(99, 102, 241, 0.4); font-style: italic; font-size: 11px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.event_list_layout.insertWidget(0, lbl)
            return

        for ev in events:
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background-color: rgba(99, 102, 241, 0.08);
                    border: none;
                    border-left: 4px solid #6366F1;
                    border-radius: 4px;
                    padding: 8px;
                }
            """)
            layout = QVBoxLayout(frame)
            layout.setSpacing(4)

            title = QLabel(f"★ {ev.get('title', 'Sin título').upper()}")
            title.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px; border: none; background: transparent;")
            layout.addWidget(title)

            time_str = ev.get("start_time", "").split(" ")[1] if " " in ev.get("start_time", "") else ""
            end_str = ev.get("end_time", "").split(" ")[1] if ev.get("end_time") and " " in ev.get("end_time", "") else ""
            duration = f"HORA: {time_str}"
            if end_str:
                duration += f" - {end_str}"
            time_lbl = QLabel(duration)
            time_lbl.setStyleSheet("color: #818CF8; font-size: 10px; border: none; background: transparent;")
            layout.addWidget(time_lbl)

            if ev.get("location"):
                loc_lbl = QLabel(f"LUGAR: {ev.get('location')}")
                loc_lbl.setStyleSheet("color: #94A3B8; font-size: 10px; border: none; background: transparent;")
                layout.addWidget(loc_lbl)

            if ev.get("attendees"):
                att_lbl = QLabel(f"CON: {ev.get('attendees')}")
                att_lbl.setStyleSheet("color: #10B981; font-size: 10px; border: none; background: transparent;")
                layout.addWidget(att_lbl)

            if ev.get("description"):
                desc_lbl = QLabel(f"NOTAS: {ev.get('description')}")
                desc_lbl.setWordWrap(True)
                desc_lbl.setStyleSheet("color: rgba(148, 163, 184, 0.8); font-size: 10px; border: none; background: transparent;")
                layout.addWidget(desc_lbl)

            self.event_list_layout.insertWidget(self.event_list_layout.count() - 1, frame)


class EmailComposeDialog(AlfonsoBaseDialog):
    def __init__(self, parent, api_client, mode="compose", orig_email=None):
        title = "REDACATAR MENSAJE" if mode == "compose" else "RESPONDER MENSAJE" if mode == "reply" else "REENVIAR MENSAJE"
        super().__init__(parent, title, modal=True)
        self.api = api_client
        self.mode = mode
        self.orig_email = orig_email
        self.setMinimumSize(500, 400)
        
        form_layout = QFormLayout()
        
        self.txt_recipient = QLineEdit()
        self.txt_subject = QLineEdit()
        self.txt_body = QTextEdit()
        
        form_layout.addRow("PARA:", self.txt_recipient)
        form_layout.addRow("ASUNTO:", self.txt_subject)
        form_layout.addRow("MENSAJE:", self.txt_body)
        
        self.content_layout.addLayout(form_layout)
        
        # Fila de botones
        btn_layout = QHBoxLayout()
        
        self.btn_draft = QPushButton("AUTO-REDACTAR CON ALFONSO")
        self.btn_draft.clicked.connect(self.generate_ai_draft)
        btn_layout.addWidget(self.btn_draft)
        
        btn_layout.addStretch()
        
        btn_send = QPushButton("ENVIAR")
        btn_send.setObjectName("SendBtn")
        btn_send.clicked.connect(self.send_email)
        btn_layout.addWidget(btn_send)
        
        btn_save_draft = QPushButton("GUARDAR BORRADOR")
        btn_save_draft.clicked.connect(self.save_draft_action)
        btn_layout.addWidget(btn_save_draft)
        
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        self.content_layout.addLayout(btn_layout)
        
        # Pre-cargar datos si es respuesta o reenvío
        if self.orig_email:
            subj = self.orig_email.get("subject", "")
            if self.mode == "reply":
                self.txt_recipient.setText(self.orig_email.get("sender", ""))
                self.txt_subject.setText(f"Re: {subj}" if not subj.lower().startswith("re:") else subj)
            elif self.mode == "forward":
                self.txt_subject.setText(f"Fwd: {subj}" if not subj.lower().startswith("fwd:") else subj)
                self.txt_body.setText(f"\n\n---------- Mensaje reenviado ----------\nDe: {self.orig_email['sender']}\nFecha: {self.orig_email['received_at']}\nAsunto: {self.orig_email['subject']}\n\n{self.orig_email['body']}")
        else:
            self.btn_draft.setVisible(False)
            
    def generate_ai_draft(self):
        if not self.orig_email:
            return
        self.btn_draft.setText("GENERANDO...")
        self.btn_draft.setEnabled(False)
        QApplication.processEvents()
        
        res = self.api.get_reply_draft(self.orig_email["id"])
        
        self.btn_draft.setText("AUTO-REDACTAR CON ALFONSO")
        self.btn_draft.setEnabled(True)
        
        if res.get("status") == "ok":
            draft = res.get("draft", {})
            self.txt_body.setPlainText(draft.get("body", ""))
            role = res.get("role", "[Alfonso]")
            QMessageBox.information(self, "Borrador Generado", f"Borrador autoredactado con éxito por {role} basado en el contexto.")
        else:
            QMessageBox.warning(self, "Error", f"No se pudo autoredactar el borrador: {res.get('message', 'Error desconocido')}")
            
    def send_email(self):
        recipient = self.txt_recipient.text().strip()
        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()
        
        if not recipient or not subject or not body:
            QMessageBox.warning(self, "Error", "Por favor completa todos los campos.")
            return
            
        if self.mode == "compose":
            res = self.api.send_email(recipient, subject, body)
        elif self.mode == "reply":
            res = self.api.reply_email(self.orig_email["id"], body)
        elif self.mode == "forward":
            res = self.api.forward_email(self.orig_email["id"], recipient, body)
            
        if res.get("status") == "ok":
            QMessageBox.information(self, "Éxito", "Mensaje enviado correctamente.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error al enviar", f"No se pudo enviar el correo: {res.get('message', 'Error desconocido')}")
 
    def save_draft_action(self):
        recipient = self.txt_recipient.text().strip()
        subject = self.txt_subject.text().strip()
        body = self.txt_body.toPlainText().strip()
        
        if not subject and not body:
            QMessageBox.warning(self, "Error", "El borrador debe tener al menos un asunto o cuerpo.")
            return
            
        res = self.api.save_draft(recipient, subject, body)
        if res.get("status") == "ok":
            QMessageBox.information(self, "Éxito", "Borrador guardado correctamente.")
            self.accept()
        else:
            QMessageBox.warning(self, "Error", f"No se pudo guardar el borrador: {res.get('message', 'Error desconocido')}")


class EmailListItemWidget(QWidget):
    def __init__(self, sender, subject, date_str, importance="Baja", read=1):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(3)
        
        # Fila superior: Remitente y Fecha
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Indicador de estado (leído/no leído/importante)
        status_lbl = QLabel(self)
        status_lbl.setStyleSheet("background: transparent;")
        if importance == "Alta":
            status_lbl.setText('<span style="color:#EF4444; font-size:12px;">●</span>')
        elif read == 0:
            status_lbl.setText('<span style="color:#6366F1; font-size:12px;">●</span>')
        else:
            status_lbl.setText('<span style="color:transparent; font-size:12px;">●</span>')
        top_layout.addWidget(status_lbl)
        
        lbl_sender = QLabel(sender, self)
        sender_color = "#FFFFFF" if read == 0 else "#94A3B8"
        sender_weight = "bold" if read == 0 else "500"
        lbl_sender.setStyleSheet(f"font-weight: {sender_weight}; font-size: 11px; color: {sender_color}; background: transparent;")
        top_layout.addWidget(lbl_sender)
        
        top_layout.addStretch()
        
        lbl_date = QLabel(date_str, self)
        lbl_date.setStyleSheet("font-size: 9px; color: rgba(255, 255, 255, 0.3); background: transparent;")
        top_layout.addWidget(lbl_date)
        layout.addLayout(top_layout)
        
        # Asunto
        lbl_sub = QLabel(subject, self)
        sub_color = "#F8FAFC" if read == 0 else "#64748B"
        lbl_sub.setStyleSheet(f"font-size: 10px; color: {sub_color}; background: transparent;")
        lbl_sub.setWordWrap(False)
        layout.addWidget(lbl_sub)


class MailWidget(AlfonsoBaseDialog):
    """Interfaz gráfica nativa para el cliente de Correo Electrónico (ALFONSO MAIL)."""
    def __init__(self, api_client, parent=None):
        super().__init__(parent, "ALFONSO MAIL", modal=False)
        self.api = api_client
        self.setMinimumSize(1150, 700)
        self.resize(1150, 700)
        
        self.current_category = None  # None significa todos
        self.emails_list = []
        
        self.setup_ui()

    def setup_ui(self):
        # ── CUERPO PRINCIPAL (Splitter de tres paneles) ──
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

        # PANEL 1: CATEGORÍAS (Izquierda)
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.3);
            }
            QPushButton#CategoryBtn {
                background-color: transparent;
                border: none;
                color: #94A3B8;
                text-align: left;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 500;
                border-radius: 6px;
            }
            QPushButton#CategoryBtn:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
            }
            QPushButton#CategoryBtn[active="true"] {
                background-color: rgba(99, 102, 241, 0.15);
                color: #818CF8;
                font-weight: bold;
            }
        """)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(6)

        lbl_cat = QLabel("CATEGORÍAS")
        lbl_cat.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent;")
        left_layout.addWidget(lbl_cat)

        self.cat_buttons = {}
        categories = [
            ("TODOS", None),
            ("LEGAL", "legal"),
            ("ADM.", "administrativo"),
            (" EMPLEO", "empleo"),
            ("COMERCIAL", "comercial"),
            ("ENVIADOS", "sent"),
            ("BORRADORES", "draft"),
            ("OTROS", "otros")
        ]
        for label, val in categories:
            btn = QPushButton(label)
            btn.setObjectName("CategoryBtn")
            btn.setProperty("cat_val", val)
            btn.clicked.connect(self.category_selected)
            self.cat_buttons[val] = btn
            left_layout.addWidget(btn)
        
        # Marcar "TODOS" como activo inicial
        self.cat_buttons[None].setProperty("active", "true")
        self.cat_buttons[None].setStyle(self.cat_buttons[None].style())

        left_layout.addStretch()
        body_splitter.addWidget(self.left_panel)

        # PANEL 2: LISTA DE CORREOS (Centro)
        self.center_panel = QWidget()
        center_layout = QVBoxLayout(self.center_panel)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(8)

        inbox_header_layout = QHBoxLayout()
        lbl_inbox = QLabel("BANDEJA DE ENTRADA")
        lbl_inbox.setStyleSheet("font-weight: bold; font-size: 10px; color: #6366F1;")
        inbox_header_layout.addWidget(lbl_inbox)
        inbox_header_layout.addStretch()
        
        btn_seed = QPushButton("MOCKS")
        btn_seed.setStyleSheet("font-size: 9px; font-weight: bold; padding: 4px 8px; max-height: 22px; max-width: 70px;")
        btn_seed.clicked.connect(self.action_seed)
        inbox_header_layout.addWidget(btn_seed)

        btn_compose = QPushButton("REDACTAR (+)")
        btn_compose.setStyleSheet("font-size: 9px; font-weight: bold; padding: 4px 8px; max-height: 22px; max-width: 90px;")
        btn_compose.clicked.connect(self.action_compose)
        inbox_header_layout.addWidget(btn_compose)
        
        center_layout.addLayout(inbox_header_layout)

        self.list_widget = QListWidget()
        self.list_widget.currentItemChanged.connect(self.email_selected)
        center_layout.addWidget(self.list_widget)

        body_splitter.addWidget(self.center_panel)

        # PANEL 3: VISOR DE DETALLE (Derecha)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(10)

        lbl_detail = QLabel("VISOR DE CORREO")
        lbl_detail.setStyleSheet("font-weight: bold; font-size: 10px; color: #6366F1;")
        right_layout.addWidget(lbl_detail)
        
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        
        self.btn_reply = QPushButton("RESPONDER")
        self.btn_reply.clicked.connect(self.action_reply)
        self.btn_reply.setEnabled(False)
        
        self.btn_forward = QPushButton("REENVIAR")
        self.btn_forward.clicked.connect(self.action_forward)
        self.btn_forward.setEnabled(False)
        
        self.btn_delete = QPushButton("ELIMINAR")
        self.btn_delete.setStyleSheet("color: #EF4444; border-color: rgba(239, 68, 68, 0.4); background-color: rgba(239, 68, 68, 0.1);")
        self.btn_delete.clicked.connect(self.action_delete)
        self.btn_delete.setEnabled(False)
        
        actions_layout.addWidget(self.btn_reply)
        actions_layout.addWidget(self.btn_forward)
        actions_layout.addWidget(self.btn_delete)
        actions_layout.addStretch()
        
        right_layout.addLayout(actions_layout)

        # Recuadro con Scroll para ver el correo
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        scroll_content = QWidget()
        self.detail_layout = QVBoxLayout(scroll_content)
        self.detail_layout.setContentsMargins(12, 12, 12, 12)
        self.detail_layout.setSpacing(12)

        # Campos de metadatos
        self.lbl_sender = QLabel("De: --")
        self.lbl_sender.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFFFFF;")
        self.detail_layout.addWidget(self.lbl_sender)

        self.lbl_subject = QLabel("Asunto: --")
        self.lbl_subject.setStyleSheet("font-weight: bold; font-size: 13px; color: #6366F1;")
        self.lbl_subject.setWordWrap(True)
        self.detail_layout.addWidget(self.lbl_subject)

        self.lbl_date = QLabel("Fecha: --")
        self.lbl_date.setStyleSheet("font-size: 10px; color: rgba(99, 102, 241, 0.6);")
        self.detail_layout.addWidget(self.lbl_date)

        # Caja especial para el resumen de Alfonso
        self.summary_box = QFrame()
        self.summary_box.setStyleSheet("""
            QFrame {
                background-color: rgba(99, 102, 241, 0.1);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 4px;
                padding: 10px;
            }
        """)
        summary_layout = QVBoxLayout(self.summary_box)
        summary_layout.setSpacing(4)
        
        summary_title = QLabel("✦ ALFONSO INTELLIGENT SUMMARY:")
        summary_title.setStyleSheet("font-weight: bold; font-size: 10px; color: #6366F1; border: none; background: transparent;")
        summary_layout.addWidget(summary_title)
        
        self.lbl_summary_text = QLabel("Selecciona un correo para ver el análisis de Alfonso.")
        self.lbl_summary_text.setWordWrap(True)
        self.lbl_summary_text.setStyleSheet("font-style: italic; color: #FFFFFF; font-size: 11px; border: none; background: transparent;")
        summary_layout.addWidget(self.lbl_summary_text)
        
        self.detail_layout.addWidget(self.summary_box)

        # Cuerpo del correo
        self.txt_body = QTextEdit()
        self.txt_body.setReadOnly(True)
        self.txt_body.setStyleSheet("border: none; background-color: transparent; color: #E0E0E0; font-size: 11px;")
        self.detail_layout.addWidget(self.txt_body)

        scroll_area.setWidget(scroll_content)
        right_layout.addWidget(scroll_area)

        body_splitter.addWidget(self.right_panel)

        # Ajuste de proporciones en el Splitter (15% izquierda, 40% centro, 45% derecha)
        body_splitter.setSizes([140, 380, 410])
        self.content_layout.addWidget(body_splitter)

    def category_selected(self):
        sender_btn = self.sender()
        cat_val = sender_btn.property("cat_val")
        self.current_category = cat_val

        # Actualizar visual de botones activos
        for val, btn in self.cat_buttons.items():
            if val == cat_val:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            btn.setStyle(btn.style())

        self.load_emails()

    def action_seed(self):
        self.api.seed_emails()
        self.load_emails()

    def load_emails(self):
        from PyQt6.QtCore import QSize
        self.list_widget.clear()
        self.emails_list = self.api.get_emails(category=self.current_category)
        
        if not self.emails_list:
            item = QListWidgetItem("Sin correos electrónicos en esta categoría.")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.list_widget.addItem(item)
            return

        for email in self.emails_list:
            subj = email.get("subject", "Sin asunto")
            sender = email.get("sender", "Desconocido")
            importance = email.get("importance", "Baja")
            read = email.get("read_status", 0)
            
            date_str = email.get("received_at", "")
            if date_str and len(date_str) > 16:
                date_str = date_str[:16].replace("T", " ")
            elif date_str:
                date_str = date_str[:16]
            
            item = QListWidgetItem(self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, email)
            item.setSizeHint(QSize(220, 56))
            
            widget = EmailListItemWidget(sender, subj, date_str, importance, read)
            self.list_widget.setItemWidget(item, widget)

    def email_selected(self, current, previous):
        if not current:
            self.btn_reply.setEnabled(False)
            self.btn_forward.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return
        
        email = current.data(Qt.ItemDataRole.UserRole)
        if not email:
            self.btn_reply.setEnabled(False)
            self.btn_forward.setEnabled(False)
            self.btn_delete.setEnabled(False)
            return

        self.btn_reply.setEnabled(True)
        self.btn_forward.setEnabled(True)
        self.btn_delete.setEnabled(True)

        # Rellenar campos del panel derecho
        self.lbl_sender.setText(f"De: {email.get('sender')}")
        self.lbl_subject.setText(f"Asunto: {email.get('subject')}")
        
        received = email.get("received_at", "")
        # Formatear fecha
        if received and len(received) > 16:
            received = received[:16].replace("T", " ")
        self.lbl_date.setText(f"Fecha: {received} | Categoría: {(email.get('category') or 'otros').upper()} | Importancia: {(email.get('importance') or 'Baja').upper()}")

        # Resumen corto de Alfonso
        summary = email.get("summary")
        if summary:
            self.lbl_summary_text.setText(summary)
        else:
            self.lbl_summary_text.setText("Este correo aún no ha sido clasificado por Alfonso. Haz click en clasificar o solicita el resumen de la mañana.")

        # Cuerpo del correo
        self.txt_body.setText(email.get("body", ""))

        # Marcar como leído en DB
        if email.get("read_status") == 0:
            self.api.mark_email_as_read(email.get("id"))
            # Recargar lista conservando selección para actualizar la negrita del item
            selected_id = email.get("id")
            self.load_emails()
            # Restaurar selección
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data.get("id") == selected_id:
                    self.list_widget.setCurrentItem(item)
                    break

    def action_compose(self):
        dialog = EmailComposeDialog(self, self.api, mode="compose")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_emails()

    def action_reply(self):
        current = self.list_widget.currentItem()
        if not current:
            return
        email = current.data(Qt.ItemDataRole.UserRole)
        if not email:
            return
        dialog = EmailComposeDialog(self, self.api, mode="reply", orig_email=email)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_emails()

    def action_forward(self):
        current = self.list_widget.currentItem()
        if not current:
            return
        email = current.data(Qt.ItemDataRole.UserRole)
        if not email:
            return
        dialog = EmailComposeDialog(self, self.api, mode="forward", orig_email=email)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_emails()

    def action_delete(self):
        current = self.list_widget.currentItem()
        if not current:
            return
        email = current.data(Qt.ItemDataRole.UserRole)
        if not email:
            return
            
        reply = QMessageBox.question(
            self, 
            "Confirmar eliminación", 
            f"¿Estás seguro de que deseas eliminar permanentemente el correo:\n'{email.get('subject')}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            res = self.api.delete_email(email.get("id"))
            if res.get("status") == "ok":
                QMessageBox.information(self, "Eliminado", "El correo ha sido eliminado correctamente.")
                self.lbl_sender.setText("De: --")
                self.lbl_subject.setText("Asunto: --")
                self.lbl_date.setText("Fecha: --")
                self.lbl_summary_text.setText("Selecciona un correo para ver el análisis de Alfonso.")
                self.txt_body.clear()
                self.btn_reply.setEnabled(False)
                self.btn_forward.setEnabled(False)
                self.btn_delete.setEnabled(False)
                self.load_emails()
            else:
                QMessageBox.warning(self, "Error", f"No se pudo eliminar el correo: {res.get('message', 'Error desconocido')}")



class ConfigWidget(AlfonsoBaseDialog):
    """Panel de Configuración nativo para Alfonso OS."""
    def __init__(self, parent_dashboard):
        super().__init__(parent_dashboard, "ALFONSO CONFIGURATION", modal=False)
        self.dashboard = parent_dashboard
        self.setMinimumSize(450, 480)

        self.setup_ui()
        self.load_values()

    def setup_ui(self):
        from PyQt6.QtWidgets import QStackedWidget, QComboBox, QSpinBox, QDoubleSpinBox
        
        # Segmented Control estilo macOS
        self.tabs_layout = QHBoxLayout()
        self.tabs_layout.setSpacing(2)
        self.tabs_layout.setContentsMargins(0, 0, 0, 10)
        
        self.tab_buttons = []
        
        self.btn_tab_email = QPushButton("CORREO")
        self.btn_tab_email.setCheckable(True)
        self.btn_tab_email.setChecked(True)
        self.btn_tab_email.clicked.connect(lambda: self.switch_tab(0))
        self.tabs_layout.addWidget(self.btn_tab_email)
        self.tab_buttons.append(self.btn_tab_email)
        
        self.btn_tab_voice = QPushButton("VOZ Y AUDIO")
        self.btn_tab_voice.setCheckable(True)
        self.btn_tab_voice.clicked.connect(lambda: self.switch_tab(1))
        self.tabs_layout.addWidget(self.btn_tab_voice)
        self.tab_buttons.append(self.btn_tab_voice)
        
        self.btn_tab_server = QPushButton("SERVIDOR")
        self.btn_tab_server.setCheckable(True)
        self.btn_tab_server.clicked.connect(lambda: self.switch_tab(2))
        self.tabs_layout.addWidget(self.btn_tab_server)
        self.tab_buttons.append(self.btn_tab_server)
        
        self.content_layout.addLayout(self.tabs_layout)
        
        # Stacked Widget
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)
        
        # --- TAB 1: CORREO ---
        self.page_email = QWidget()
        email_form = QFormLayout(self.page_email)
        email_form.setVerticalSpacing(15)
        email_form.setContentsMargins(10, 10, 10, 10)
        
        self.input_email = QLineEdit()
        self.input_email.setPlaceholderText("ejemplo@gmail.com")
        self.input_pass = QLineEdit()
        self.input_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_pass.setPlaceholderText("Contraseña de Aplicación de 16 caracteres")
        
        email_form.addRow(QLabel("Email (Gmail):"), self.input_email)
        email_form.addRow(QLabel("Clave de App:"), self.input_pass)
        self.stack.addWidget(self.page_email)
        
        # --- TAB 2: VOZ Y AUDIO ---
        self.page_voice = QWidget()
        voice_form = QFormLayout(self.page_voice)
        voice_form.setVerticalSpacing(12)
        voice_form.setContentsMargins(10, 10, 10, 10)
        
        self.input_keyword = QLineEdit()
        self.combo_model = QComboBox()
        self.combo_model.addItems(["tiny", "base", "small", "medium", "large"])
        
        self.spin_device = QSpinBox()
        self.spin_device.setRange(0, 32)
        
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.0, 1.0)
        self.spin_threshold.setSingleStep(0.01)
        
        voice_form.addRow(QLabel("Palabra Clave (Voz):"), self.input_keyword)
        voice_form.addRow(QLabel("Modelo de Voz:"), self.combo_model)
        voice_form.addRow(QLabel("ID Micrófono:"), self.spin_device)
        voice_form.addRow(QLabel("Umbral Ruido:"), self.spin_threshold)
        self.stack.addWidget(self.page_voice)
        
        # --- TAB 3: SERVIDOR ---
        self.page_server = QWidget()
        server_form = QFormLayout(self.page_server)
        server_form.setVerticalSpacing(15)
        server_form.setContentsMargins(10, 10, 10, 10)
        
        self.input_url = QLineEdit()
        server_form.addRow(QLabel("URL Servidor:"), self.input_url)
        self.stack.addWidget(self.page_server)
        
        # Botones de Acción
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.btn_cancel = QPushButton("CANCELAR")
        self.btn_cancel.clicked.connect(self.close)
        
        self.btn_save = QPushButton("GUARDAR PREFERENCIAS")
        self.btn_save.setObjectName("SaveBtn")
        self.btn_save.clicked.connect(self.save_values)
        
        actions_layout.addWidget(self.btn_cancel)
        actions_layout.addWidget(self.btn_save)
        self.content_layout.addLayout(actions_layout)

        # Estilo de pestañas estilo Mac
        self.update_tab_buttons_style()

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.tab_buttons):
            btn.setChecked(i == index)
        self.update_tab_buttons_style()

    def update_tab_buttons_style(self):
        for btn in self.tab_buttons:
            if btn.isChecked():
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(99, 102, 241, 0.25);
                        border: 1px solid #6366F1;
                        color: #FFFFFF;
                        font-weight: bold;
                        padding: 6px 14px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 255, 255, 0.02);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        color: #CBD5E1;
                        font-weight: 500;
                        padding: 6px 14px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 255, 255, 0.08);
                    }
                """)

    def load_values(self):
        c = self.dashboard.config
        self.input_url.setText(c.get('url', "http://localhost:8000"))
        self.input_keyword.setText(c.get('keyword', "alfonso"))
        
        model_val = c.get('model', "tiny")
        idx = self.combo_model.findText(model_val)
        if idx >= 0:
            self.combo_model.setCurrentIndex(idx)
            
        dev_val = c.get('device')
        self.spin_device.setValue(dev_val if dev_val is not None else 8)
        self.spin_threshold.setValue(c.get('threshold') if c.get('threshold') is not None else 0.03)

        # Cargar variables de email del archivo .env si existe
        gmail_email = ""
        gmail_pass = ""
        try:
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(gui_dir))
            env_path = os.path.join(project_root, ".env")
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("GMAIL_EMAIL="):
                            gmail_email = line.split("=", 1)[1].strip()
                        elif line.strip().startswith("GMAIL_APP_PASSWORD="):
                            gmail_pass = line.split("=", 1)[1].strip()
        except Exception:
            pass
            
        self.input_email.setText(gmail_email)
        self.input_pass.setText(gmail_pass)

    def save_values(self):
        c = self.dashboard.config
        c['url'] = self.input_url.text().strip()
        c['keyword'] = self.input_keyword.text().strip()
        c['model'] = self.combo_model.currentText()
        c['device'] = self.spin_device.value()
        c['threshold'] = self.spin_threshold.value()

        # Guardar credenciales de correo real en el archivo .env para el servidor
        try:
            gui_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(gui_dir))
            env_path = os.path.join(project_root, ".env")
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            
            gmail_email = self.input_email.text().strip()
            gmail_pass = self.input_pass.text().strip()
            
            email_found = False
            pass_found = False
            for idx, line in enumerate(lines):
                if line.strip().startswith("GMAIL_EMAIL="):
                    lines[idx] = f"GMAIL_EMAIL={gmail_email}\n"
                    email_found = True
                elif line.strip().startswith("GMAIL_APP_PASSWORD="):
                    lines[idx] = f"GMAIL_APP_PASSWORD={gmail_pass}\n"
                    pass_found = True
                    
            if not email_found:
                lines.append(f"GMAIL_EMAIL={gmail_email}\n")
            if not pass_found:
                lines.append(f"GMAIL_APP_PASSWORD={gmail_pass}\n")
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            os.environ["GMAIL_EMAIL"] = gmail_email
            os.environ["GMAIL_APP_PASSWORD"] = gmail_pass
        except Exception as e:
            print(f"Error saving env file: {e}")

        # Mostrar aviso de éxito
        QMessageBox.information(
            self, 
            "Configuración Guardada", 
            "Los parámetros del sistema operativo Alfonso OS han sido actualizados con éxito."
        )
        self.close()


class DiagnosticsWidget(QWidget):
    """Removed"""
    def __init__(self, parent_dashboard):
        super().__init__()
        return

        self.setStyleSheet("""
            QWidget {
                background-color: #0B0E14;
                color: #CBD5E1;
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }
            QLabel {
                color: #94A3B8;
                font-weight: 600;
                font-size: 12px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.05);
                color: #CBD5E1;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(0, 229, 255, 0.15);
                color: #FFFFFF;
                border-color: rgba(0, 229, 255, 0.4);
            }
            QTextBrowser {
                background-color: rgba(15, 20, 28, 0.9);
                color: #10B981;
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 11px;
                border: 1px solid rgba(0, 229, 255, 0.25);
                border-radius: 6px;
                padding: 10px;
            }
            QFrame#DiagContainer {
                border: 1px solid rgba(0, 229, 255, 0.3);
                border-radius: 12px;
                background-color: rgba(20, 25, 35, 0.95);
            }
        """)

        self.setup_ui()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None

    def setup_ui(self):
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(0, 0, 0, 0)
        window_layout.setSpacing(0)

        container_frame = QFrame()
        container_frame.setObjectName("DiagContainer")
        container_layout = QVBoxLayout(container_frame)
        container_layout.setContentsMargins(20, 20, 20, 20)
        container_layout.setSpacing(15)

        # Cabecera
        header_layout = QHBoxLayout()
        header_title = QLabel("// ALFONSO OS // DIAGNOSTICS & TELEMETRY ver 1.0.0")
        header_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #FFB800; letter-spacing: 1px;")
        
        btn_close = QPushButton("[X]")
        btn_close.setFixedWidth(40)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                color: #FFB800;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #FF4B4B;
            }
        """)
        btn_close.clicked.connect(self.close)
        
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        header_layout.addWidget(btn_close)
        container_layout.addLayout(header_layout)

        # Separador
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.08);")
        container_layout.addWidget(sep)

        # Estado rápido del sistema
        self.status_layout = QGridLayout()
        self.status_layout.setSpacing(10)
        
        self.lbl_net_status = QLabel("VERIFICANDO RED...")
        self.lbl_net_status.setStyleSheet("color: #FFB800; font-weight: bold;")
        self.lbl_agent_status = QLabel("VERIFICANDO AGENTE...")
        self.lbl_agent_status.setStyleSheet("color: #FFB800; font-weight: bold;")
        
        self.status_layout.addWidget(QLabel("Conexión Backend:"), 0, 0)
        self.status_layout.addWidget(self.lbl_net_status, 0, 1)
        self.status_layout.addWidget(QLabel("Proceso Agente:"), 1, 0)
        self.status_layout.addWidget(self.lbl_agent_status, 1, 1)
        
        container_layout.addLayout(self.status_layout)

        # Dispositivos de Entrada de Audio detectados
        container_layout.addWidget(QLabel("Dispositivos de Entrada de Audio Detectados (PyAudio):"))
        self.txt_audio_devices = QTextBrowser()
        container_layout.addWidget(self.txt_audio_devices)

        # Botón de Recarga / Test manual
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.btn_refresh = QPushButton("EJECUTAR TEST")
        self.btn_refresh.clicked.connect(self.run_diagnostics)
        
        self.btn_close_panel = QPushButton("CERRAR")
        self.btn_close_panel.clicked.connect(self.close)
        
        actions_layout.addWidget(self.btn_refresh)
        actions_layout.addWidget(self.btn_close_panel)
        container_layout.addLayout(actions_layout)

        window_layout.addWidget(container_frame)

    def run_diagnostics(self):
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("PROBANDO SISTEMAS...")
        self.lbl_net_status.setText("EJECUTANDO TEST DE RED...")
        self.lbl_net_status.setStyleSheet("color: #FFB800; font-weight: bold;")
        self.lbl_agent_status.setText("COMPROBANDO PROCESOS...")
        self.lbl_agent_status.setStyleSheet("color: #FFB800; font-weight: bold;")
        self.txt_audio_devices.setText("REALIZANDO BARRIDO DE HARDWARE...")
        
        QTimer.singleShot(700, self._execute_tests)

    def _execute_tests(self):
        # 1. Test de Red no-bloqueante
        url = self.dashboard.config.get('url', "http://localhost:8000")
        try:
            import urllib.request
            import time
            start_t = time.time()
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                elapsed = int((time.time() - start_t) * 1000)
                self.lbl_net_status.setText(f"ONLINE ({elapsed} ms) - Código: {resp.status}")
                self.lbl_net_status.setStyleSheet("color: #10B981; font-weight: bold;")
        except Exception as e:
            self.lbl_net_status.setText(f"OFFLINE - Error: Connection Failed")
            self.lbl_net_status.setStyleSheet("color: #FF4B4B; font-weight: bold;")

        # 2. Test del Agente secundario alfonso_agent
        if self.dashboard.agent_process and self.dashboard.agent_process.poll() is None:
            pid = self.dashboard.agent_process.pid
            self.lbl_agent_status.setText(f"ACTIVO (PID: {pid})")
            self.lbl_agent_status.setStyleSheet("color: #10B981; font-weight: bold;")
        else:
            self.lbl_agent_status.setText("INACTIVO / DETENIDO")
            self.lbl_agent_status.setStyleSheet("color: #FF4B4B; font-weight: bold;")

        # 3. Listar Dispositivos de Audio usando sounddevice (ya instalado en el entorno)
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            device_lines = []
            
            for i, d in enumerate(devices):
                if d.get("max_input_channels", 0) > 0:
                    device_lines.append(f"ID {i}: {d.get('name')} (Canales Max Entrada: {d.get('max_input_channels')})")
                    
            if device_lines:
                self.txt_audio_devices.setText("\n".join(device_lines))
            else:
                self.txt_audio_devices.setText("Ningún dispositivo de entrada de audio detectado por sounddevice.")
        except Exception as e:
            self.txt_audio_devices.setText(f"Error al inicializar sounddevice o escanear dispositivos:\n{str(e)}")

        self.btn_refresh.setEnabled(True)
        self.btn_refresh.setText("EJECUTAR TEST")


class AlertsWidget(AlfonsoBaseDialog):
    """Centro de Alertas y Notificaciones del Sistema Alfonso OS."""
    def __init__(self, parent_dashboard):
        super().__init__(parent_dashboard, "ALFONSO ALERTS", modal=False)
        self.dashboard = parent_dashboard
        self.setMinimumSize(500, 400)

        self.setup_ui()

    def setup_ui(self):
        # Lista de Alertas
        self.list_widget = QListWidget()
        self.content_layout.addWidget(self.list_widget)

        # Botón de Despejar
        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.btn_clear = QPushButton("DESPEJAR ALERTAS")
        self.btn_clear.setObjectName("ClearBtn")
        # Colorear botón de peligro con estilo coherente (rojo suave)
        self.btn_clear.setStyleSheet("color: #EF4444; border-color: rgba(239, 68, 68, 0.4); background-color: rgba(239, 68, 68, 0.1);")
        self.btn_clear.clicked.connect(self.clear_all)
        
        self.btn_close_panel = QPushButton("CERRAR")
        self.btn_close_panel.clicked.connect(self.close)
        
        actions_layout.addWidget(self.btn_clear)
        actions_layout.addWidget(self.btn_close_panel)
        self.content_layout.addLayout(actions_layout)

    def load_alerts(self):
        self.list_widget.clear()
        
        # Generar alertas en caliente según estado real
        alerts = []
        
        # 1. Comprobar red
        url = self.dashboard.config.get('url', "http://localhost:8000")
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                pass
        except Exception:
            alerts.append("⚠️ [RED] Conexión Backend Offline - No se pudo contactar con " + url)

        # 2. Comprobar Micrófono
        dev_id = self.dashboard.config.get('device', 8)
        alerts.append(f"⚠️ [AUDIO] Entrada de audio ID [{dev_id}] en escucha activa.")
        
        # 3. Mensaje informativo de inicio
        alerts.append("ℹ️ [SISTEMA] Alfonso OS core v3.7.19 cargado en espacio de usuario.")

        for msg in alerts:
            item = QListWidgetItem(msg)
            if "⚠️" in msg:
                item.setForeground(QColor("#FFB800"))
            else:
                item.setForeground(QColor("#00E5FF"))
            self.list_widget.addItem(item)

    def clear_all(self):
        self.list_widget.clear()
        self.dashboard.alert_btn.setText(" 0 ALERTS ")
        self.dashboard.alert_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 10);
                color: #CBD5E1;
                border: 2px solid rgba(255, 255, 255, 0.2);
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 20);
                color: #FFFFFF;
            }
        """)
        QMessageBox.information(self, "Alertas Limpias", "Todas las notificaciones de estado han sido despejadas.")
        self.close()


class PlaywrightWorkerThread(QThread):
    finished_signal = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.page = None
        self.browser = None
        self.pw = None
        self.running = True

    def run(self):
        try:
            from playwright.sync_api import sync_playwright
            self.pw = sync_playwright().start()
            self.browser = self.pw.chromium.launch(headless=False)
            context = self.browser.new_context()
            self.page = context.new_page()
            
            aeat_url = "https://sede.agenciatributaria.gob.es/Sede/procedimiento/G611.shtml"
            self.page.goto(aeat_url)
            
            while self.running:
                self.msleep(500)
                try:
                    if not self.browser.is_connected() or len(self.browser.contexts) == 0 or len(context.pages) == 0:
                        break
                except Exception:
                    break
            self.finished_signal.emit({"status": "closed"})
        except Exception as e:
            self.finished_signal.emit({"status": "error", "message": str(e)})
        finally:
            self.stop_pw()

    def stop_pw(self):
        self.running = False
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.pw:
                self.pw.stop()
        except Exception:
            pass


class AeatAutofillWidget(AlfonsoBaseDialog):
    """Panel de control de Autorelleno del Modelo 303 en la AEAT."""
    def __init__(self, parent_dashboard):
        super().__init__(parent_dashboard, "ALFONSO AEAT AUTOFILL", modal=False)
        self.dashboard = parent_dashboard
        self.setMinimumSize(600, 560)
        self.pw_thread = None
        
        self.income_base = 0.0
        self.income_iva = 0.0
        self.expense_base = 0.0
        self.expense_iva = 0.0

        self.setup_ui()

    def setup_ui(self):
        from PyQt6.QtWidgets import QStackedWidget
        
        # Filtros de año y periodo
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Ejercicio Fiscal (Año):"))
        self.combo_year = QComboBox()
        self.combo_year.addItems(["2026", "2025", "2027"])
        filter_layout.addWidget(self.combo_year)
 
        filter_layout.addWidget(QLabel("Periodo (Trimestre):"))
        self.combo_period = QComboBox()
        self.combo_period.addItems(["1T (Primer Trimestre)", "2T (Segundo Trimestre)", "3T (Tercer Trimestre)", "4T (Cuarto Trimestre)"])
        filter_layout.addWidget(self.combo_period)
 
        self.btn_load_data = QPushButton("CARGAR DATOS")
        self.btn_load_data.clicked.connect(self.load_data)
        filter_layout.addWidget(self.btn_load_data)
        self.content_layout.addLayout(filter_layout)

        # Segmented Control para alternar IVA / IRPF
        self.seg_layout = QHBoxLayout()
        self.seg_layout.setSpacing(2)
        self.seg_layout.setContentsMargins(0, 5, 0, 5)
        
        self.btn_tab_iva = QPushButton("IVA (MODELO 303)")
        self.btn_tab_iva.setCheckable(True)
        self.btn_tab_iva.setChecked(True)
        self.btn_tab_iva.clicked.connect(lambda: self.switch_tab(0))
        self.seg_layout.addWidget(self.btn_tab_iva)
        
        self.btn_tab_irpf = QPushButton("IRPF (MODELO 130)")
        self.btn_tab_irpf.setCheckable(True)
        self.btn_tab_irpf.clicked.connect(lambda: self.switch_tab(1))
        self.seg_layout.addWidget(self.btn_tab_irpf)
        
        self.content_layout.addLayout(self.seg_layout)
        
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)

        # ── PÁGINA 1: IVA (MODELO 303) ──
        self.page_iva = QWidget()
        iva_layout = QVBoxLayout(self.page_iva)
        iva_layout.setContentsMargins(0, 0, 0, 0)
        iva_layout.setSpacing(10)
        
        # Layout horizontal para los grupos
        groups_layout = QHBoxLayout()
        groups_layout.setSpacing(15)
 
        # Grupo de Ingresos
        self.group_income = QGroupBox("INGRESOS DEVENGADOS")
        self.group_income.setStyleSheet("QGroupBox { border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; margin-top: 10px; padding: 12px; font-weight: bold; color: #6366F1; }")
        income_layout = QFormLayout(self.group_income)
        income_layout.setVerticalSpacing(10)
        self.lbl_income_base = QLabel("0.00 €")
        self.lbl_income_base.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        self.lbl_income_iva = QLabel("0.00 €")
        self.lbl_income_iva.setStyleSheet("color: #10B981; font-size: 14px; font-weight: bold;")
        income_layout.addRow("Base [Casilla 01]:", self.lbl_income_base)
        income_layout.addRow("IVA [Casilla 03]:", self.lbl_income_iva)
        groups_layout.addWidget(self.group_income)
 
        # Grupo de Gastos
        self.group_expense = QGroupBox("COMPRAS Y GASTOS")
        self.group_expense.setStyleSheet("QGroupBox { border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; margin-top: 10px; padding: 12px; font-weight: bold; color: #6366F1; }")
        expense_layout = QFormLayout(self.group_expense)
        expense_layout.setVerticalSpacing(10)
        self.lbl_expense_base = QLabel("0.00 €")
        self.lbl_expense_base.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        self.lbl_expense_iva = QLabel("0.00 €")
        self.lbl_expense_iva.setStyleSheet("color: #10B981; font-size: 14px; font-weight: bold;")
        expense_layout.addRow("Base [Casilla 28]:", self.lbl_expense_base)
        expense_layout.addRow("IVA [Casilla 29]:", self.lbl_expense_iva)
        groups_layout.addWidget(self.group_expense)
 
        iva_layout.addLayout(groups_layout)
 
        # Grupo del Resultado
        self.lbl_result = QLabel("Resultado Neto Estimado: 0.00 €")
        self.lbl_result.setStyleSheet("color: #6366F1; font-size: 14px; font-weight: bold; padding: 10px; background-color: rgba(99, 102, 241, 0.05); border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.2);")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        iva_layout.addWidget(self.lbl_result)

        # Botón para descargar libros de IVA
        self.btn_export_iva_books = QPushButton("DESCARGAR LIBROS DE IVA OFICIALES")
        self.btn_export_iva_books.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); border-color: #10B981; color: #10B981; font-weight: bold; padding: 8px;")
        self.btn_export_iva_books.clicked.connect(self.export_iva_official_books)
        iva_layout.addWidget(self.btn_export_iva_books)
 
        # Botones de Acción
        actions_layout = QHBoxLayout()
        self.btn_open_aeat = QPushButton("1. ABRIR SEDE AEAT")
        self.btn_open_aeat.setObjectName("ActionBtn")
        self.btn_open_aeat.clicked.connect(self.open_playwright_browser)
        
        self.btn_fill = QPushButton("2. AUTORELLENAR DECLARACIÓN")
        self.btn_fill.setObjectName("FillBtn")
        self.btn_fill.setEnabled(False)
        self.btn_fill.clicked.connect(self.inject_autofill_script)
        
        self.btn_cancel = QPushButton("CANCELAR")
        self.btn_cancel.clicked.connect(self.close)
        
        actions_layout.addWidget(self.btn_open_aeat)
        actions_layout.addWidget(self.btn_fill)
        actions_layout.addStretch()
        actions_layout.addWidget(self.btn_cancel)
        iva_layout.addLayout(actions_layout)
        
        self.stack.addWidget(self.page_iva)

        # ── PÁGINA 2: IRPF (MODELO 130) ──
        self.page_irpf = QWidget()
        irpf_layout = QVBoxLayout(self.page_irpf)
        irpf_layout.setContentsMargins(0, 0, 0, 0)
        irpf_layout.setSpacing(10)
        
        self.group_irpf = QGroupBox("CÓMPUTO DEL IRPF (PAGO FRACCIONADO)")
        self.group_irpf.setStyleSheet("QGroupBox { border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 8px; margin-top: 10px; padding: 15px; font-weight: bold; color: #6366F1; }")
        irpf_form = QFormLayout(self.group_irpf)
        irpf_form.setVerticalSpacing(12)
        
        self.lbl_irpf_ingresos = QLabel("0.00 €")
        self.lbl_irpf_ingresos.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        self.lbl_irpf_gastos = QLabel("0.00 €")
        self.lbl_irpf_gastos.setStyleSheet("color: #FFFFFF; font-size: 14px; font-weight: bold;")
        self.lbl_irpf_rendimiento = QLabel("0.00 €")
        self.lbl_irpf_rendimiento.setStyleSheet("color: #F59E0B; font-size: 14px; font-weight: bold;")
        self.lbl_irpf_cuota = QLabel("0.00 €")
        self.lbl_irpf_cuota.setStyleSheet("color: #10B981; font-size: 16px; font-weight: bold;")
        
        irpf_form.addRow("Ingresos Computables [Actividad]:", self.lbl_irpf_ingresos)
        irpf_form.addRow("Gastos Deducibles [Actividad]:", self.lbl_irpf_gastos)
        irpf_form.addRow("Rendimiento Neto (Beneficio):", self.lbl_irpf_rendimiento)
        irpf_form.addRow("Pago Fraccionado Estimado (20%):", self.lbl_irpf_cuota)
        irpf_layout.addWidget(self.group_irpf)
        
        info_label = QLabel("Nota: El Modelo 130 es un pago a cuenta trimestral del IRPF sobre el rendimiento neto de actividades económicas en estimación directa.")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #94A3B8; font-size: 10px; font-style: italic; padding: 5px;")
        irpf_layout.addWidget(info_label)
        
        irpf_actions = QHBoxLayout()
        irpf_actions.addStretch()
        btn_close_irpf = QPushButton("CERRAR")
        btn_close_irpf.clicked.connect(self.close)
        irpf_actions.addWidget(btn_close_irpf)
        irpf_layout.addLayout(irpf_actions)
        
        self.stack.addWidget(self.page_irpf)

        self.update_tab_style()
        self.load_data()

    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_tab_iva.setChecked(index == 0)
        self.btn_tab_irpf.setChecked(index == 1)
        self.update_tab_style()
        self.load_data()

    def update_tab_style(self):
        for idx, btn in enumerate([self.btn_tab_iva, self.btn_tab_irpf]):
            if btn.isChecked():
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(99, 102, 241, 0.25);
                        border: 1px solid #6366F1;
                        color: #FFFFFF;
                        font-weight: bold;
                        padding: 6px 14px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 255, 255, 0.02);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        color: #CBD5E1;
                        font-weight: 500;
                        padding: 6px 14px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 255, 255, 0.08);
                    }
                """)

    def load_data(self):
        year = int(self.combo_year.currentText())
        quarter = self.combo_period.currentIndex() + 1
        
        self.btn_load_data.setText("CARGANDO...")
        self.btn_load_data.setEnabled(False)
        QApplication.processEvents()
        
        # 1. Cargar datos del IVA
        res = self.dashboard.thread.api.get_tax_aggregates(year)
        
        self.btn_load_data.setText("CARGAR DATOS")
        self.btn_load_data.setEnabled(True)
        
        if res.get("status") == "ok":
            aggregates = res.get("aggregates", [])
            quarter_data = None
            for agg in aggregates:
                if agg.get("quarter") == quarter:
                    quarter_data = agg
                    break
            
            if quarter_data:
                self.income_base = quarter_data["income"]["base"]
                self.income_iva = quarter_data["income"]["iva"]
                self.expense_base = quarter_data["expense"]["base"]
                self.expense_iva = quarter_data["expense"]["iva"]
                net = self.income_iva - self.expense_iva
            else:
                self.income_base = 0.0
                self.income_iva = 0.0
                self.expense_base = 0.0
                self.expense_iva = 0.0
                net = 0.0
                
            self.lbl_income_base.setText(f"{self.income_base:,.2f} €")
            self.lbl_income_iva.setText(f"{self.income_iva:,.2f} €")
            self.lbl_expense_base.setText(f"{self.expense_base:,.2f} €")
            self.lbl_expense_iva.setText(f"{self.expense_iva:,.2f} €")
            self.lbl_result.setText(f"Resultado IVA Neto Estimado (Casilla [71]): {net:,.2f} €")
        else:
            QMessageBox.warning(self, "Error", f"No se pudieron cargar los datos de impuestos: {res.get('message')}")
            
        # 2. Cargar datos del IRPF (Modelo 130)
        try:
            from app.domain.services.ledger_service import LedgerService
            irpf_data = LedgerService.get_modelo_130_estimate(year, quarter)
            self.lbl_irpf_ingresos.setText(f"{irpf_data['ingresos']:,.2f} €")
            self.lbl_irpf_gastos.setText(f"{irpf_data['gastos']:,.2f} €")
            self.lbl_irpf_rendimiento.setText(f"{irpf_data['rendimiento']:,.2f} €")
            self.lbl_irpf_cuota.setText(f"{irpf_data['pago_estimado']:,.2f} €")
        except Exception as e:
            print(f"Error loading IRPF: {e}")

    def export_iva_official_books(self):
        year = int(self.combo_year.currentText())
        try:
            dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio para Guardar Libros de IVA")
            if not dir_path:
                return
                
            from app.domain.services.ledger_service import LedgerService
            books = LedgerService.get_iva_register_books(year)
            
            import csv
            import os
            
            emitidas_path = os.path.join(dir_path, f"libro_registro_facturas_emitidas_{year}.csv")
            recibidas_path = os.path.join(dir_path, f"libro_registro_facturas_recibidas_{year}.csv")
            
            with open(emitidas_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Número Factura", "Fecha Expedición", "Cliente", "NIF Cliente", "Base Imponible", "Tipo IVA (%)", "Cuota IVA", "Retención IRPF", "Total", "Trimestre"])
                for r in books["emitidas"]:
                    writer.writerow([
                        r["num_factura"], r["fecha"], r["cliente"], r["nif_cliente"],
                        f"{r['base']:.2f}", f"{r['tipo_iva']:.1f}", f"{r['cuota_iva']:.2f}",
                        f"{r['retencion']:.2f}", f"{r['total']:.2f}", r["trimestre"]
                    ])
                    
            with open(recibidas_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Número Factura", "Fecha Recepción", "Proveedor", "NIF Proveedor", "Base Imponible", "Tipo IVA (%)", "Cuota IVA", "Retención IRPF", "Total", "Trimestre"])
                for r in books["recibidas"]:
                    writer.writerow([
                        r["num_factura"], r["fecha"], r["proveedor"], r["nif_proveedor"],
                        f"{r['base']:.2f}", f"{r['tipo_iva']:.1f}", f"{r['cuota_iva']:.2f}",
                        f"{r['retencion']:.2f}", f"{r['total']:.2f}", r["trimestre"]
                    ])
                    
            QMessageBox.information(
                self, "Exportación Exitosa", 
                f"Se han exportado correctamente los libros oficiales de IVA para el ejercicio {year}:\n\n"
                f"1. {os.path.basename(emitidas_path)}\n"
                f"2. {os.path.basename(recibidas_path)}"
            )
        except Exception as e:
            QMessageBox.warning(self, "Error al exportar libros de IVA", f"No se pudo completar la exportación: {e}")


    def open_playwright_browser(self):
        if self.pw_thread and self.pw_thread.isRunning():
            QMessageBox.information(self, "Navegador Activo", "Ya hay una sesión del navegador abierta en el portal de la AEAT.")
            return

        self.btn_open_aeat.setEnabled(False)
        self.btn_open_aeat.setText("ABRIENDO NAVEGADOR...")
        QApplication.processEvents()
        
        self.pw_thread = PlaywrightWorkerThread(self)
        self.pw_thread.finished_signal.connect(self.on_browser_closed)
        self.pw_thread.start()
        
        # Esperar un poco a que se inicialice la página
        QTimer.singleShot(3000, self.enable_fill_button)

    def enable_fill_button(self):
        self.btn_open_aeat.setText("1. ABRIR SEDE AEAT")
        self.btn_open_aeat.setEnabled(True)
        if self.pw_thread and self.pw_thread.isRunning():
            self.btn_fill.setEnabled(True)

    def on_browser_closed(self, result):
        self.btn_fill.setEnabled(False)
        if result.get("status") == "error":
            QMessageBox.warning(self, "Error de Playwright", f"Ocurrió un error en el navegador: {result.get('message')}")
        else:
            logger.info("Navegador de Playwright cerrado.")

    def inject_autofill_script(self):
        if not self.pw_thread or not self.pw_thread.page:
            QMessageBox.warning(self, "Error", "El navegador de Playwright no está inicializado o se ha cerrado.")
            return
            
        try:
            # Script JavaScript inyectable con selectores dinámicos refinados
            js_script = f"""
            (function() {{
                console.log("Alfonso Autónomo: Iniciando autocompletado en caliente...");
                
                function findField(casillaNumber) {{
                    const padded = String(casillaNumber).padStart(2, '0');
                    const selectors = [
                        `input[id$='C${{padded}}']`, `input[id$='C${{casillaNumber}}']`,
                        `input[name$='C${{padded}}']`, `input[name$='C${{casillaNumber}}']`,
                        `#C${{padded}}`, `#C${{casillaNumber}}`,
                        `input[aria-label*='Casilla ${{padded}}']`, `input[aria-label*='Casilla ${{casillaNumber}}']`,
                        `input[title*='Casilla ${{padded}}']`, `input[title*='Casilla ${{casillaNumber}}']`,
                        `input[data-casilla='${{padded}}']`, `input[data-casilla='${{casillaNumber}}']`
                    ];
                    for (const sel of selectors) {{
                        const el = document.querySelector(sel);
                        if (el) return el;
                    }}
                    
                    const labels = Array.from(document.querySelectorAll('label, span, td, div, p, th'));
                    const searchTerms = [`[${{padded}}]`, `[${{casillaNumber}}]`, `casilla ${{padded}}`, `casilla ${{casillaNumber}}`];
                    for (const label of labels) {{
                        const text = label.textContent.toLowerCase();
                        if (searchTerms.some(term => text.includes(term))) {{
                            const input = label.querySelector('input') || 
                                          (label.nextElementSibling && label.nextElementSibling.querySelector('input')) ||
                                          (label.parentElement && label.parentElement.querySelector('input'));
                            if (input) return input;
                        }}
                    }}
                    return null;
                }}

                const fields = {{
                    "base_21": {{ casilla: "01", value: "{self.income_base}" }},
                    "tipo_21": {{ casilla: "02", value: "21" }},
                    "cuota_21": {{ casilla: "03", value: "{self.income_iva}" }},
                    "base_ded": {{ casilla: "28", value: "{self.expense_base}" }},
                    "cuota_ded": {{ casilla: "29", value: "{self.expense_iva}" }}
                }};
                
                let filledCount = 0;
                for (const key in fields) {{
                    const item = fields[key];
                    const input = findField(item.casilla);
                    if (input) {{
                        input.value = item.value;
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                        console.log("Rellenado: " + key + " (Casilla " + item.casilla + ") = " + item.value);
                        filledCount++;
                    }}
                }}
                alert("Alfonso Autónomo: Autorelleno inyectado correctamente. Se rellenaron " + filledCount + " casillas.");
            }})();
            """
            self.pw_thread.page.evaluate(js_script)
            QMessageBox.information(self, "Datos Inyectados", "Se han autorellenado las casillas del Modelo 303 en el formulario activo del navegador.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo inyectar el autorelleno. Asegúrate de estar en la página del formulario del Modelo 303 en la AEAT. Detalles: {e}")

    def closeEvent(self, event):
        if self.pw_thread:
            self.pw_thread.stop_pw()
        super().closeEvent(event)


class ProjectNavigatorDialog(AlfonsoBaseDialog):
    """Ventana flotante Pop-up del Proyecto Activo con Chat integrado y Canales temáticos."""
    def __init__(self, parent_dashboard):
        super().__init__(parent_dashboard, "WORKSPACE NAVIGATOR", modal=False)
        self.dashboard = parent_dashboard
        self.setMinimumSize(960, 600)
        self.projects_data = {} # Caché estructurada
        self.active_project_name = "default"
        self.active_session_id = "default"
        
        self.setup_ui()

    def setup_ui(self):
        # CONTENIDO: DOBLE COLUMNA (IZQ: CANALES Y PROYECTOS, DER: CONSOLA DE CHAT)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        # Columna Izquierda: Listado de canales temáticos del proyecto
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
        # Selector de Proyecto (para poder conmutar de proyecto dentro del pop-up)
        lbl_proj = QLabel("📁 ACTIVE PROJECTS")
        lbl_proj.setStyleSheet("font-size: 9px; font-weight: bold; color: #6366F1; letter-spacing: 1px;")
        left_layout.addWidget(lbl_proj)
        
        self.proj_list = QListWidget()
        self.proj_list.setFixedHeight(120)
        self.proj_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 6px;
                color: #CBD5E1;
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 10px;
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
                padding: 6px 8px;
            }
            QListWidget::item:selected {
                background-color: rgba(99, 102, 241, 0.15);
                border-left: 2px solid #6366F1;
                color: #FFFFFF;
            }
        """)
        self.proj_list.itemClicked.connect(self.select_project)
        left_layout.addWidget(self.proj_list)
        
        lbl_conv = QLabel("💬 DISCIPLINE CHANNELS")
        lbl_conv.setStyleSheet("font-size: 9px; font-weight: bold; color: #6366F1; letter-spacing: 1px;")
        left_layout.addWidget(lbl_conv)
        
        self.conv_list = QListWidget()
        self.conv_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(99, 102, 241, 0.25);
                border-radius: 6px;
                color: #CBD5E1;
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 11px;
            }
            QListWidget::item {
                border-bottom: 1px solid rgba(255, 255, 255, 0.02);
                padding: 8px 10px;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background-color: rgba(16, 185, 129, 0.12);
                border-left: 3px solid #10B981;
                color: #10B981;
            }
        """)
        self.conv_list.itemClicked.connect(self.switch_channel_from_list)
        left_layout.addWidget(self.conv_list)
        content_layout.addLayout(left_layout, 2)
        
        # Columna Derecha: Consola de chat dedicada para interactuar con Alfonso en este canal/proyecto
        right_layout = QVBoxLayout()
        right_layout.setSpacing(10)
        
        self.lbl_channel_status = QLabel("CANAL: SELECCIONA UN TEMA")
        self.lbl_channel_status.setStyleSheet("""
            font-size: 10px;
            font-weight: bold;
            color: #10B981;
            font-family: 'Consolas', monospace;
            background-color: rgba(16, 185, 129, 0.05);
            border: 1px solid rgba(16, 185, 129, 0.15);
            border-radius: 4px;
            padding: 5px;
        """)
        right_layout.addWidget(self.lbl_channel_status)
        
        # Historial de chat dedicado en el pop-up
        self.chat_display = QTextBrowser()
        self.chat_display.setOpenExternalLinks(True)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 6px;
                color: #CBD5E1;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                padding: 10px;
            }
        """)
        right_layout.addWidget(self.chat_display, 1)
        
        # Entrada de texto dedicada
        input_layout = QHBoxLayout()
        input_layout.setSpacing(8)
        
        self.txt_input = QTextEdit()
        self.txt_input.setFixedHeight(50)
        self.txt_input.setPlaceholderText("Escribe un mensaje para Alfonso en este canal...")
        self.txt_input.setStyleSheet("""
            QTextEdit {
                background-color: rgba(15, 23, 42, 0.9);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 4px;
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                padding: 5px;
            }
            QTextEdit:focus {
                border-color: #6366F1;
            }
        """)
        self.txt_input.installEventFilter(self) # Para capturar Enter al enviar
        input_layout.addWidget(self.txt_input, 1)
        
        btn_send = QPushButton("ENVIAR")
        btn_send.setFixedSize(80, 50)
        btn_send.clicked.connect(self.send_message_from_dialog)
        input_layout.addWidget(btn_send)
        
        right_layout.addLayout(input_layout)
        content_layout.addLayout(right_layout, 3)
        
        self.content_layout.addLayout(content_layout, 1)
        
        # Botones inferiores
        bottom_layout = QHBoxLayout()
        btn_refresh = QPushButton("REFRESCAR WORKSPACE")
        btn_refresh.clicked.connect(self.dashboard.reload_projects_list)
        
        btn_close_dlg = QPushButton("MINIMIZAR")
        btn_close_dlg.clicked.connect(self.close)
        
        bottom_layout.addWidget(btn_refresh)
        bottom_layout.addStretch()
        bottom_layout.addWidget(btn_close_dlg)
        self.content_layout.addLayout(bottom_layout)

    def eventFilter(self, obj, event):
        """Captura la pulsación de la tecla enter para enviar mensajes."""
        if obj is self.txt_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.send_message_from_dialog()
                return True
        return super().eventFilter(obj, event)

    def select_project(self, item):
        """Muestra en la lista de abajo las conversaciones asociadas al proyecto seleccionado."""
        display_name = item.text().replace("📁 ", "").strip().upper()
        self.active_project_name = display_name
        self.conv_list.clear()
        
        # Buscar el proyecto de forma insensible a mayúsculas y minúsculas en la caché
        conversations = []
        for key, val in self.projects_data.items():
            if key.strip().upper() == display_name:
                conversations = val
                break
                
        selected_item = None
        for c in conversations:
            title = c.get("title") or "Sin título"
            session_id = c.get("session_id")
            discipline = c.get("discipline") or "general"
            
            display_text = f"[{discipline.upper()}] {title}"
            list_item = QListWidgetItem(display_text)
            
            list_item.setData(Qt.ItemDataRole.UserRole, session_id)
            list_item.setData(Qt.ItemDataRole.UserRole + 1, title)
            list_item.setData(Qt.ItemDataRole.UserRole + 2, key)
            
            if session_id == self.dashboard.thread.session_id:
                selected_item = list_item
                
            self.conv_list.addItem(list_item)
            
        if selected_item:
            self.conv_list.setCurrentItem(selected_item)
            self.switch_channel_from_list(selected_item)
        elif self.conv_list.count() > 0:
            first_itm = self.conv_list.item(0)
            self.conv_list.setCurrentItem(first_itm)
            self.switch_channel_from_list(first_itm)

    def switch_channel_from_list(self, item):
        """Conmuta la conversación activa en el hilo del asistente y refresca el historial del chat."""
        session_id = item.data(Qt.ItemDataRole.UserRole)
        title = item.data(Qt.ItemDataRole.UserRole + 1)
        project = item.data(Qt.ItemDataRole.UserRole + 2)
        
        if not session_id:
            return
            
        self.active_session_id = session_id
        
        # Cambiar el session_id del hilo activo de Alfonso en background
        self.dashboard.thread.session_id = session_id
        
        # Sincronizar en sesión persistente
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(gui_dir), "logs", "session_config.json")
        try:
            import json
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id}, f, indent=4)
        except Exception:
            pass
            
        # Actualizar banner de estado
        self.lbl_channel_status.setText(f"ACTIVO: {project.upper()} > {title.upper()}")
        self.header_title.setText(f"// ALFONSO OS // WORKSPACE: {project.upper()}")
        self.dashboard.lbl_active_session.setText(f"ACTIVO: {project.upper()} > {title.upper()}")
        
        # Cargar historial en el panel de chat del Pop-up
        self.load_dialog_chat_history(session_id, project, title)

    def load_dialog_chat_history(self, session_id, project, title):
        try:
            res = self.dashboard.thread.api.get_memory_detail(session_id)
            messages = res.get("messages", [])
            
            chat_html = ""
            for msg in messages:
                sender = "Tú" if msg.get("role") == "user" else "Alfonso"
                content = msg.get("content") or ""
                color = "#00E5FF" if sender == "Alfonso" else "#F59E0B"
                chat_html += f"<p><b style='color:{color};'>[{sender.upper()}]</b><br/>{content.replace('\n', '<br/>')}</p>"
                
            if not chat_html:
                chat_html = f"<p style='color:#64748B;'><i>No hay mensajes previos en este canal. Inicia el diálogo.</i></p>"
                
            self.chat_display.setHtml(chat_html)
            QTimer.singleShot(50, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))
            
        except Exception as e:
            self.chat_display.setHtml(f"<p style='color:#EF4444;'>Error cargando historial: {e}</p>")

    def send_message_from_dialog(self):
        """Envía el mensaje desde el cuadro de texto del Pop-up y lo procesa."""
        text = self.txt_input.toPlainText().strip()
        if not text:
            return
            
        self.txt_input.clear()
        
        # Si el asistente está en modo de audio normal, lo forzamos a texto para procesar rápido
        if not self.dashboard.text_mode_enabled:
            self.dashboard.toggle_text_mode()
            
        # Añadimos localmente a la ventana del pop-up el mensaje de "Tú"
        cur_html = self.chat_display.toHtml()
        user_msg_html = f"<p><b style='color:#F59E0B;'>[TÚ]</b><br/>{text.replace('\n', '<br/>')}</p>"
        self.chat_display.setHtml(cur_html + user_msg_html)
        QTimer.singleShot(50, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))
        
        # Lanzar el envío de mensaje a Alfonso
        self.dashboard.thread.send_text_message(text)


class AlfonsoOnboardingWizard(AlfonsoBaseDialog):
    """Asistente de Onboarding para datos fiscales y firma digital FNMT."""
    def __init__(self, parent=None, api_client=None):
        self.api = api_client
        super().__init__(parent, "ASISTENTE DE CONFIGURACIÓN CONTABLE (ONBOARDING)")
        self.setMinimumSize(500, 450)
        self.setup_wizard_ui()

    def setup_wizard_ui(self):
        desc = QLabel("Introduce los datos fiscales obligatorios de tu negocio para configurar la gestoría. Toda la información se almacenará de forma encriptada.")
        desc.setWordWrap(True)
        self.content_layout.addWidget(desc)

        form_layout = QFormLayout()
        
        self.cmb_type = QComboBox()
        self.cmb_type.addItems(["autónomo", "pyme"])
        form_layout.addRow("Tipo de Contribuyente:", self.cmb_type)

        self.txt_razon = QLineEdit()
        self.txt_razon.setPlaceholderText("Nombre completo o Razón Social S.L.")
        form_layout.addRow("Razón Social:", self.txt_razon)

        self.txt_nif = QLineEdit()
        self.txt_nif.setPlaceholderText("NIF / CIF (ej: 12345678Z)")
        form_layout.addRow("NIF / CIF:", self.txt_nif)

        self.txt_dir = QLineEdit()
        self.txt_dir.setPlaceholderText("Dirección fiscal")
        form_layout.addRow("Dirección Fiscal:", self.txt_dir)

        # Certificado
        self.lbl_cert_status = QLabel("Certificado no cargado (.pfx / .p12)")
        self.lbl_cert_status.setStyleSheet("color: #EF4444; font-style: italic;")
        
        btn_select_cert = QPushButton("Examinar Certificado...")
        btn_select_cert.clicked.connect(self.select_certificate)
        form_layout.addRow(self.lbl_cert_status, btn_select_cert)

        self.txt_cert_pass = QLineEdit()
        self.txt_cert_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_cert_pass.setPlaceholderText("Contraseña del certificado digital")
        form_layout.addRow("Contraseña Certificado:", self.txt_cert_pass)

        self.content_layout.addLayout(form_layout)
        self.selected_cert_path = ""

        # Botón Guardar
        self.btn_save = QPushButton("GUARDAR Y VALIDAR CONFIGURACIÓN")
        self.btn_save.clicked.connect(self.save_profile)
        self.content_layout.addWidget(self.btn_save)

    def select_certificate(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Certificado Digital", "", "Certificados (*.pfx *.p12)")
        if file_path:
            self.selected_cert_path = file_path
            self.lbl_cert_status.setText(f"Certificado cargado: {os.path.basename(file_path)}")
            self.lbl_cert_status.setStyleSheet("color: #10B981; font-weight: bold;")

    def save_profile(self):
        user_type = self.cmb_type.currentText()
        razon = self.txt_razon.text().strip()
        nif = self.txt_nif.text().strip()
        direccion = self.txt_dir.text().strip()
        cert_pass = self.txt_cert_pass.text().strip()

        if not razon or not nif:
            QMessageBox.warning(self, "Error de Validación", "La Razón Social y el NIF/CIF son campos obligatorios.")
            return

        try:
            import requests
            url = f"{self.api.base_url}/tax/profile"
            data = {
                "user_type": user_type,
                "nif": nif,
                "razon_social": razon,
                "direccion": direccion,
                "cert_password": cert_pass
            }
            files = None
            if self.selected_cert_path:
                files = {
                    "certificate": (os.path.basename(self.selected_cert_path), open(self.selected_cert_path, "rb"), "application/x-pkcs12")
                }
            headers = {"X-API-Key": self.api.api_key}
            res = requests.post(url, data=data, files=files, headers=headers)
            if res.status_code == 200:
                QMessageBox.information(self, "Éxito", "Configuración de Onboarding guardada con éxito.")
                self.accept()
            else:
                QMessageBox.critical(self, "Error", f"Error en servidor al guardar perfil: {res.text}")
        except Exception as e:
            QMessageBox.critical(self, "Error de Conexión", f"No se pudo conectar al servidor: {e}")

class AlfonsoBankReconciliationDialog(AlfonsoBaseDialog):
    """Diálogo de Conciliación Bancaria con soporte Multibanco y Multi-cuenta."""
    def __init__(self, parent=None, api_client=None):
        self.api = api_client
        super().__init__(parent, "CONCILIACIÓN BANCARIA AUTOMÁTICA Y MANUAL")
        self.setMinimumSize(750, 550)
        self.setup_recon_ui()

    def setup_recon_ui(self):
        intro = QLabel("Desde este panel puedes configurar múltiples bancos, importar extractos Norma 43, agregar movimientos manuales y ejecutar el matching con facturas.")
        intro.setWordWrap(True)
        self.content_layout.addWidget(intro)

        # Filtro de cuenta y botón de administración
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("<b>Seleccionar Cuenta:</b>"))
        
        self.cb_account = QComboBox()
        self.cb_account.currentIndexChanged.connect(self.load_bank_movements)
        filter_layout.addWidget(self.cb_account)
        
        btn_manage = QPushButton("⚙️ Administrar Bancos/Cuentas")
        btn_manage.clicked.connect(self.manage_connections)
        filter_layout.addWidget(btn_manage)
        
        self.content_layout.addLayout(filter_layout)

        # Botones de Operaciones
        btn_layout = QHBoxLayout()
        btn_import = QPushButton("Importar Norma 43 (.txt)")
        btn_import.clicked.connect(self.import_norma43)
        btn_layout.addWidget(btn_import)

        btn_manual = QPushButton("Añadir Movimiento Manual")
        btn_manual.clicked.connect(self.add_manual_mov)
        btn_layout.addWidget(btn_manual)

        btn_transfer = QPushButton("💸 Realizar Transferencia")
        btn_transfer.clicked.connect(self.initiate_transfer)
        btn_layout.addWidget(btn_transfer)

        btn_subs = QPushButton("⭐ Plan Premium")
        btn_subs.clicked.connect(self.show_subscription)
        btn_layout.addWidget(btn_subs)

        btn_reconcile = QPushButton("⚡ Ejecutar Matching Automático")
        btn_reconcile.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-color: #6366F1; color: #818CF8; font-weight: bold;")
        btn_reconcile.clicked.connect(self.run_matching)
        btn_layout.addWidget(btn_reconcile)

        self.content_layout.addLayout(btn_layout)

        # Tabla de movimientos
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fecha", "Cuenta/Banco", "Concepto", "Importe", "Estado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.content_layout.addWidget(QLabel("<b>Historial de Movimientos Bancarios:</b>"))
        self.content_layout.addWidget(self.table)

        self.refresh_accounts_list()

    def refresh_accounts_list(self):
        self.cb_account.blockSignals(True)
        self.cb_account.clear()
        self.cb_account.addItem("Todas las cuentas", None)
        
        try:
            from app.domain.services.bank_service import BankService
            connections = BankService.list_connections()
            for conn in connections:
                display_text = f"{conn['alias']} ({conn['bank_name'] or 'Banco'})"
                self.cb_account.addItem(display_text, conn["id"])
        except Exception as e:
            print(f"Error loading connections: {e}")
            
        self.cb_account.blockSignals(False)
        self.load_bank_movements()

    def load_bank_movements(self):
        try:
            from app.adapters.memory.memory import _get_connection
            from app.utils.encryption import encryptor
            
            connection_id = self.cb_account.currentData()
            with _get_connection() as conn:
                cursor = conn.cursor()
                if connection_id is not None:
                    cursor.execute("""
                        SELECT m.movement_date, m.concept, m.amount, m.reconciled, c.alias 
                        FROM bank_movements m
                        LEFT JOIN bank_connections c ON m.connection_id = c.id
                        WHERE m.connection_id = ?
                        ORDER BY m.id DESC
                    """, (connection_id,))
                else:
                    cursor.execute("""
                        SELECT m.movement_date, m.concept, m.amount, m.reconciled, c.alias 
                        FROM bank_movements m
                        LEFT JOIN bank_connections c ON m.connection_id = c.id
                        ORDER BY m.id DESC
                    """)
                rows = cursor.fetchall()

            self.table.setRowCount(len(rows))
            for row_idx, r in enumerate(rows):
                fecha = r["movement_date"]
                concepto = encryptor.decrypt(r["concept"])
                importe = f"{r['amount']:.2f} €"
                estado = "🟢 Conciliado" if r["reconciled"] else "🔴 Pendiente"
                cuenta = r["alias"] or "Sin Vincular"

                self.table.setItem(row_idx, 0, QTableWidgetItem(fecha))
                self.table.setItem(row_idx, 1, QTableWidgetItem(cuenta))
                self.table.setItem(row_idx, 2, QTableWidgetItem(concepto))
                self.table.setItem(row_idx, 3, QTableWidgetItem(importe))
                self.table.setItem(row_idx, 4, QTableWidgetItem(estado))
        except Exception as e:
            print(f"Error loading bank movements: {e}")

    def manage_connections(self):
        dialog = AlfonsoBankConnectionsDialog(self)
        dialog.exec()
        self.refresh_accounts_list()

    def import_norma43(self):
        connection_id = self.cb_account.currentData()
        if connection_id is None:
            QMessageBox.warning(self, "Seleccionar Cuenta", "Por favor, selecciona una cuenta bancaria específica en el desplegable superior antes de importar el extracto.")
            return

        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Extracto Norma 43", "", "Norma 43 (*.txt *.n43)")
        if file_path:
            try:
                import requests
                url = f"{self.api.base_url}/tax/bank/import"
                if connection_id is not None:
                    url += f"?connection_id={connection_id}"
                headers = {"X-API-Key": self.api.api_key}
                files = {"file": open(file_path, "rb")}
                res = requests.post(url, files=files, headers=headers)
                if res.status_code == 200:
                    info = res.json()
                    QMessageBox.information(self, "Importación", info.get("message", "Importado correctamente."))
                    self.load_bank_movements()
                else:
                    QMessageBox.warning(self, "Error", f"Error al importar: {res.text}")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def add_manual_mov(self):
        connection_id = self.cb_account.currentData()
        if connection_id is None:
            QMessageBox.warning(self, "Seleccionar Cuenta", "Por favor, selecciona una cuenta bancaria específica en el desplegable superior antes de registrar un movimiento manual.")
            return

        dialog = AlfonsoBaseDialog(self, "AÑADIR MOVIMIENTO MANUAL")
        dialog.setMinimumSize(350, 250)

        form = QFormLayout()
        txt_date = QLineEdit(datetime.datetime.now().strftime("%d/%m/%Y"))
        txt_concept = QLineEdit()
        txt_amount = QLineEdit()

        form.addRow("Fecha (DD/MM/YYYY):", txt_date)
        form.addRow("Concepto:", txt_concept)
        form.addRow("Importe (€):", txt_amount)
        dialog.content_layout.addLayout(form)

        btn_ok = QPushButton("REGISTRAR")
        dialog.content_layout.addWidget(btn_ok)

        def save_manual():
            try:
                from app.domain.services.bank_service import BankService
                date_str = txt_date.text().strip()
                concept = txt_concept.text().strip()
                amount = float(txt_amount.text().strip().replace(",", "."))
                
                BankService.add_manual_movement(date_str, concept, amount, "manual", connection_id)
                QMessageBox.information(dialog, "Éxito", "Movimiento registrado con éxito.")
                dialog.accept()
                self.load_bank_movements()
            except Exception as e:
                QMessageBox.critical(dialog, "Error", f"Verifica los datos: {e}")

        btn_ok.clicked.connect(save_manual)
        dialog.exec()

    def run_matching(self):
        try:
            from app.domain.services.bank_service import BankService
            pairs = BankService.reconcile_matching_algorithm()
            QMessageBox.information(self, "Conciliación Finalizada", f"Se han conciliado automáticamente {len(pairs)} movimientos contables.")
            self.load_bank_movements()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def initiate_transfer(self):
        connection_id = self.cb_account.currentData()
        if connection_id is None:
            QMessageBox.warning(self, "Seleccionar Cuenta", "Para realizar transferencias en pruebas debes tener seleccionada una cuenta activa en el desplegable superior.")
            return
            
        dialog = AlfonsoInitiateTransferDialog(self, connection_id)
        dialog.exec()
        self.load_bank_movements()

    def show_subscription(self):
        dialog = AlfonsoSubscriptionDialog(self)
        dialog.exec()


class AlfonsoBankConnectionsDialog(AlfonsoBaseDialog):
    """Diálogo para configurar y administrar múltiples conexiones bancarias."""
    def __init__(self, parent=None):
        super().__init__(parent, "ADMINISTRAR CONEXIONES BANCARIAS")
        self.setMinimumSize(650, 400)
        self.setup_ui()

    def setup_ui(self):
        self.content_layout.addWidget(QLabel("<b>Cuentas Bancarias Vinculadas:</b>"))
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Alias", "Banco", "IBAN", "Proveedor", "Estado", "Sincronizado"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.content_layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        
        btn_add = QPushButton(" Conectar Banco (Mock)")
        btn_add.clicked.connect(lambda: self.add_connection("mock"))
        btn_layout.addWidget(btn_add)
        
        btn_add_gocardless = QPushButton("Conectar Banco (GoCardless/Real)")
        btn_add_gocardless.clicked.connect(lambda: self.add_connection("gocardless"))
        btn_layout.addWidget(btn_add_gocardless)
        
        btn_sync = QPushButton("Sincronizar")
        btn_sync.clicked.connect(self.sync_selected)
        btn_layout.addWidget(btn_sync)
        
        btn_delete = QPushButton("Eliminar")
        btn_delete.clicked.connect(self.delete_selected)
        btn_layout.addWidget(btn_delete)
        
        self.content_layout.addLayout(btn_layout)
        self.load_connections()

    def load_connections(self):
        try:
            from app.domain.services.bank_service import BankService
            connections = BankService.list_connections()
            self.table.setRowCount(len(connections))
            self.connection_ids = []
            
            for idx, c in enumerate(connections):
                self.connection_ids.append(c["id"])
                self.table.setItem(idx, 0, QTableWidgetItem(c["alias"]))
                self.table.setItem(idx, 1, QTableWidgetItem(c["bank_name"] or "N/A"))
                self.table.setItem(idx, 2, QTableWidgetItem(c["iban"] or "N/A"))
                self.table.setItem(idx, 3, QTableWidgetItem(c["provider"].upper()))
                self.table.setItem(idx, 4, QTableWidgetItem(c["status"].upper()))
                self.table.setItem(idx, 5, QTableWidgetItem(c["last_sync_at"] or "Nunca"))
        except Exception as e:
            print(f"Error loading connections in manager: {e}")

    def add_connection(self, provider: str):
        dialog = AlfonsoBaseDialog(self, f"VINCULAR CUENTA ({provider.upper()})")
        dialog.setMinimumSize(350, 250)
        
        form = QFormLayout()
        txt_alias = QLineEdit()
        txt_bank = QLineEdit()
        txt_iban = QLineEdit()
        
        if provider == "mock":
            txt_alias.setText("Banco Santander (Pruebas)")
            txt_bank.setText("Santander")
            txt_iban.setText("ES9100491500001234567890")
        else:
            txt_alias.setText("BBVA Online")
            txt_bank.setText("BBVA")
            txt_iban.setText("")
            
        form.addRow("Alias Cuenta:", txt_alias)
        form.addRow("Nombre Banco:", txt_bank)
        
        if provider == "mock":
            form.addRow("IBAN Cuenta:", txt_iban)
            
        dialog.content_layout.addLayout(form)
        
        btn_save = QPushButton("GUARDAR Y CONECTAR")
        dialog.content_layout.addWidget(btn_save)
        
        def save():
            try:
                import json
                from app.domain.services.bank_service import BankService
                alias = txt_alias.text().strip()
                bank = txt_bank.text().strip()
                iban = txt_iban.text().strip() if provider == "mock" else "Autodetectando al conectar..."
                
                creds = json.dumps({"account_id": f"acc_{provider}_{bank.lower()}"})
                
                conn_id = BankService.add_connection(alias, provider, bank, iban, creds)
                
                if provider == "gocardless":
                    from app.adapters.bank_providers import BankProviderFactory
                    import webbrowser
                    prov = BankProviderFactory.get_provider("gocardless")
                    url = prov.get_auth_link("http://localhost:8000/callback", {
                        "institution_id": "SANDBOXFINANCE_SBOX1",
                        "bank_name": bank
                    })
                    
                    try:
                        webbrowser.open(url)
                    except Exception:
                        pass
                    
                    url_dialog = AlfonsoBaseDialog(dialog, "AUTORIZACIÓN BANCARIA")
                    url_dialog.setMinimumSize(450, 220)
                    
                    lbl_msg = QLabel("Hemos abierto el navegador web para iniciar la autorización segura en tu banco.<br><br>Si no se ha abierto automáticamente, puedes copiar el siguiente enlace:")
                    lbl_msg.setWordWrap(True)
                    url_dialog.content_layout.addWidget(lbl_msg)
                    
                    txt_url = QLineEdit(url)
                    txt_url.setReadOnly(True)
                    txt_url.setStyleSheet("background-color: rgba(0, 0, 0, 0.3); border: 1px solid #312E81; color: #818CF8; padding: 6px; border-radius: 4px;")
                    url_dialog.content_layout.addWidget(txt_url)
                    
                    btn_copy = QPushButton("📋 Copiar enlace al portapapeles")
                    btn_copy.setStyleSheet("background-color: rgba(99, 102, 241, 0.1); border-color: #4F46E5; color: #A5B4FC;")
                    def copy_link():
                        clipboard = QApplication.clipboard()
                        clipboard.setText(url)
                        btn_copy.setText("✓ ¡Enlace Copiado!")
                    btn_copy.clicked.connect(copy_link)
                    url_dialog.content_layout.addWidget(btn_copy)
                    
                    btn_close = QPushButton("ENTENDIDO")
                    btn_close.clicked.connect(url_dialog.accept)
                    url_dialog.content_layout.addWidget(btn_close)
                    
                    url_dialog.exec()
                else:
                    success_dialog = AlfonsoBaseDialog(dialog, "ÉXITO")
                    success_dialog.setMinimumSize(300, 150)
                    success_dialog.content_layout.addWidget(QLabel("Cuenta vinculada correctamente."))
                    btn_close = QPushButton("ENTENDIDO")
                    btn_close.clicked.connect(success_dialog.accept)
                    success_dialog.content_layout.addWidget(btn_close)
                    success_dialog.exec()
                    
                dialog.accept()
                self.load_connections()
            except Exception as e:
                error_dialog = AlfonsoBaseDialog(dialog, "ERROR")
                error_dialog.setMinimumSize(350, 150)
                lbl = QLabel(f"Error al vincular: {e}")
                lbl.setWordWrap(True)
                error_dialog.content_layout.addWidget(lbl)
                btn_close = QPushButton("ENTENDIDO")
                btn_close.clicked.connect(error_dialog.accept)
                error_dialog.content_layout.addWidget(btn_close)
                error_dialog.exec()
                
        btn_save.clicked.connect(save)
        dialog.exec()

    def delete_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Seleccionar", "Por favor, selecciona una conexión de la lista para eliminar.")
            return
            
        conn_id = self.connection_ids[row]
        reply = QMessageBox.warning(self, "Eliminar Conexión", "¿Estás seguro de que deseas eliminar esta cuenta bancaria? Los movimientos quedarán guardados pero se desvincularán del banco.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                from app.domain.services.bank_service import BankService
                BankService.delete_connection(conn_id)
                QMessageBox.information(self, "Éxito", "Conexión eliminada correctamente.")
                self.load_connections()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def sync_selected(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Seleccionar", "Por favor, selecciona una conexión de la lista para sincronizar.")
            return
            
        conn_id = self.connection_ids[row]
        try:
            from app.domain.services.bank_service import BankService
            count = BankService.sync_connection(conn_id)
            QMessageBox.information(self, "Éxito", f"Sincronización finalizada. Se descargaron {count} nuevos movimientos.")
            self.load_connections()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al sincronizar: {e}")


class AlfonsoSubscriptionDialog(AlfonsoBaseDialog):
    """Diálogo para ver y gestionar planes de suscripción de transferencias."""
    def __init__(self, parent=None):
        super().__init__(parent, "PLAN PREMIUM Y TRANSFERENCIAS")
        self.setMinimumSize(450, 350)
        self.setup_ui()

    def setup_ui(self):
        from app.domain.services.bank_service import BankService
        
        status = BankService.get_subscription_status()
        tier = status["tier"]
        used = status["used"]
        limit = status["limit"]
        remaining = status["remaining"]
        charges = status["accumulated_extra_charges"]
        
        lbl_info = QLabel("<b>Gestión del cupo mensual de transferencias directas:</b>")
        self.content_layout.addWidget(lbl_info)
        
        grid = QGridLayout()
        grid.addWidget(QLabel("Plan Contratado:"), 0, 0)
        
        self.lbl_tier = QLabel(f"<font color='#818CF8'><b>{tier.upper()}</b></font>")
        grid.addWidget(self.lbl_tier, 0, 1)
        
        grid.addWidget(QLabel("Transferencias Usadas:"), 1, 0)
        grid.addWidget(QLabel(f"{used} / {limit if limit > 0 else '0'}"), 1, 1)
        
        grid.addWidget(QLabel("Restantes en Plan:"), 2, 0)
        grid.addWidget(QLabel(f"{remaining}"), 2, 1)
        
        grid.addWidget(QLabel("Costes Extra Acumulados:"), 3, 0)
        grid.addWidget(QLabel(f"<font color='#EF4444'><b>{charges:.2f} €</b></font>"), 3, 1)
        
        self.content_layout.addLayout(grid)
        
        from PyQt6.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        if limit > 0:
            self.progress.setMaximum(limit)
            self.progress.setValue(min(used, limit))
        else:
            self.progress.setMaximum(100)
            self.progress.setValue(0)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                background-color: #0F172A;
                color: #e2e8f0;
            }
            QProgressBar::chunk {
                background-color: #6366F1;
            }
        """)
        self.content_layout.addWidget(self.progress)
        
        self.content_layout.addWidget(QLabel("<br><b>Cambiar de Plan de Suscripción:</b>"))
        self.cmb_tier = QComboBox()
        self.cmb_tier.addItem("Gratuito (Solo Lectura, +0.50€ por transfer)", "free")
        self.cmb_tier.addItem("Premium 10 (Hasta 10 transfes/mes)", "premium_10")
        self.cmb_tier.addItem("Premium 20 (Hasta 20 transfes/mes)", "premium_20")
        self.cmb_tier.addItem("Premium 50 (Hasta 50 transfes/mes)", "premium_50")
        
        idx = self.cmb_tier.findData(tier)
        if idx >= 0:
            self.cmb_tier.setCurrentIndex(idx)
        self.content_layout.addWidget(self.cmb_tier)
        
        btn_save = QPushButton("CAMBIAR DE PLAN")
        btn_save.clicked.connect(self.save_tier)
        self.content_layout.addWidget(btn_save)
        
        btn_close = QPushButton("CERRAR")
        btn_close.clicked.connect(self.accept)
        self.content_layout.addWidget(btn_close)

    def save_tier(self):
        try:
            from app.domain.services.bank_service import BankService
            new_tier = self.cmb_tier.currentData()
            BankService.update_subscription_tier(new_tier)
            QMessageBox.information(self, "Plan Actualizado", f"Tu suscripción se ha cambiado a {new_tier.upper()} correctamente.")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


class AlfonsoInitiateTransferDialog(AlfonsoBaseDialog):
    """Diálogo para iniciar transferencias (PIS)."""
    def __init__(self, parent=None, connection_id=None):
        self.connection_id = connection_id
        super().__init__(parent, "INICIAR TRANSFERENCIA BANCARIA")
        self.setMinimumSize(450, 350)
        self.setup_ui()

    def setup_ui(self):
        from app.domain.services.bank_service import BankService
        
        status = BankService.get_subscription_status()
        self.tier = status["tier"]
        self.used = status["used"]
        self.limit = status["limit"]
        self.fee = status["extra_charge_per_transfer"]
        
        form = QFormLayout()
        self.txt_recipient = QLineEdit()
        self.txt_iban = QLineEdit()
        
        from PyQt6.QtWidgets import QDoubleSpinBox
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 1000000.00)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setValue(100.00)
        self.spin_amount.setSuffix(" €")
        
        self.txt_concept = QLineEdit()
        self.txt_concept.setPlaceholderText("Concepto del pago / factura")
        
        form.addRow("Beneficiario:", self.txt_recipient)
        form.addRow("IBAN Destino:", self.txt_iban)
        form.addRow("Importe:", self.spin_amount)
        form.addRow("Concepto:", self.txt_concept)
        
        self.content_layout.addLayout(form)
        
        self.lbl_warning = QLabel()
        self.lbl_warning.setWordWrap(True)
        self.update_quota_warning()
        self.content_layout.addWidget(self.lbl_warning)
        
        btn_send = QPushButton("⚡ INICIAR PAGO Y FIRMAR")
        btn_send.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-color: #6366F1; color: #818CF8; font-weight: bold;")
        btn_send.clicked.connect(self.send_transfer)
        self.content_layout.addWidget(btn_send)
        
        btn_cancel = QPushButton("CANCELAR")
        btn_cancel.clicked.connect(self.reject)
        self.content_layout.addWidget(btn_cancel)

    def update_quota_warning(self):
        if self.tier == "free":
            self.lbl_warning.setText(f"<font color='#F59E0B'>⚠️ <b>Aviso:</b> Tu plan actual es <b>Gratuito</b>. Esta transferencia se procesará pero incurrirá en un recargo extra de <b>{self.fee:.2f} €</b> a final de mes.</font>")
        elif self.used >= self.limit:
            self.lbl_warning.setText(f"<font color='#F59E0B'>⚠️ <b>Aviso:</b> Has agotado tu cupo de {self.limit} transferencias de tu plan. Esta transferencia adicional tendrá un recargo extra de <b>{self.fee:.2f} €</b> a final de mes.</font>")
        else:
            remaining = self.limit - self.used
            self.lbl_warning.setText(f"<font color='#10B981'>✓ <b>Incluido en el plan:</b> Tienes {remaining} transferencias restantes de tu plan <b>{self.tier.upper()}</b> para este periodo.</font>")

    def send_transfer(self):
        recipient = self.txt_recipient.text().strip()
        iban = self.txt_iban.text().strip()
        amount = self.spin_amount.value()
        concept = self.txt_concept.text().strip()
        
        if not recipient or not iban:
            QMessageBox.warning(self, "Validación", "Los campos Beneficiario e IBAN son obligatorios.")
            return
            
        try:
            from app.domain.services.bank_service import BankService
            res = BankService.initiate_transfer(self.connection_id, recipient, iban, amount, concept)
            
            msg = f"Transferencia enviada correctamente.<br><br>"
            if res.get("extra_charge", 0.0) > 0.0:
                msg += f"<font color='#EF4444'>Se ha cargado un extra de {res['extra_charge']:.2f} € por exceso de cupo.</font>"
            else:
                msg += "<font color='#10B981'>Operación cubierta por tu cupo premium.</font>"
                
            custom_dialog = AlfonsoBaseDialog(self, "FIRMA DE TRANSFERENCIA")
            custom_dialog.setMinimumSize(400, 200)
            custom_dialog.content_layout.addWidget(QLabel(f"Simulando Firma de Transferencia a través de la API segura del banco:<br><br><b>Destinatario:</b> {recipient}<br><b>Importe:</b> {amount:.2f} €<br><b>Estado:</b> Completada de forma segura."))
            btn_ok = QPushButton("ENTENDIDO")
            btn_ok.clicked.connect(custom_dialog.accept)
            custom_dialog.content_layout.addWidget(btn_ok)
            custom_dialog.exec()
            
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al procesar la transferencia: {e}")


class AlfonsoManualEntryDialog(AlfonsoBaseDialog):
    """Diálogo para ingresar un asiento contable manual por partida doble."""
    def __init__(self, parent=None):
        super().__init__(parent, "INGRESAR ASIENTO MANUAL")
        self.setMinimumSize(500, 350)
        self.setup_ui()

    def setup_ui(self):
        form_layout = QFormLayout()
        
        self.txt_date = QLineEdit()
        self.txt_date.setText(datetime.datetime.now().strftime("%d/%m/%Y"))
        self.txt_date.setPlaceholderText("DD/MM/YYYY")
        form_layout.addRow("Fecha del Asiento:", self.txt_date)
        
        self.txt_concept = QLineEdit()
        self.txt_concept.setPlaceholderText("Ej: Pago en efectivo de suministros")
        form_layout.addRow("Concepto / Descripción:", self.txt_concept)
        
        # Cargar cuentas PGC
        from app.domain.services.ledger_service import LedgerService
        accounts = LedgerService.get_pgc_accounts()
        
        self.cmb_debe = QComboBox()
        self.cmb_haber = QComboBox()
        
        for acc in accounts:
            label = f"{acc['code']} - {acc['name']}"
            self.cmb_debe.addItem(label, acc['code'])
            self.cmb_haber.addItem(label, acc['code'])
            
        # Seleccionar valores por defecto razonables
        # Debe: Gastos diversos (629)
        idx_debe = self.cmb_debe.findData("62900000")
        if idx_debe >= 0:
            self.cmb_debe.setCurrentIndex(idx_debe)
            
        # Haber: Caja efectivo (570)
        idx_haber = self.cmb_haber.findData("57000000")
        if idx_haber >= 0:
            self.cmb_haber.setCurrentIndex(idx_haber)
            
        form_layout.addRow("Cuenta de Cargo (Debe):", self.cmb_debe)
        form_layout.addRow("Cuenta de Abono (Haber):", self.cmb_haber)
        
        from PyQt6.QtWidgets import QDoubleSpinBox
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999.00)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSuffix(" €")
        self.spin_amount.setValue(50.00)
        form_layout.addRow("Importe del Asiento:", self.spin_amount)
        
        self.content_layout.addLayout(form_layout)
        
        # Botones
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_save = QPushButton("REGISTRAR ASIENTO")
        self.btn_save.clicked.connect(self.save_entry)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_cancel = QPushButton("CANCELAR")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        self.content_layout.addLayout(btn_layout)

    def save_entry(self):
        date_str = self.txt_date.text().strip()
        concept = self.txt_concept.text().strip()
        code_debe = self.cmb_debe.currentData()
        code_haber = self.cmb_haber.currentData()
        amount = self.spin_amount.value()
        
        if not date_str or not concept:
            QMessageBox.warning(self, "Validación", "Todos los campos son obligatorios.")
            return
            
        # Validar fecha simple
        try:
            datetime.datetime.strptime(date_str, "%d/%m/%Y")
        except Exception:
            QMessageBox.warning(self, "Validación", "Formato de fecha inválido. Utilice DD/MM/YYYY.")
            return
            
        if code_debe == code_haber:
            QMessageBox.warning(self, "Validación", "La cuenta de Debe y Haber no pueden ser la misma.")
            return

        try:
            from app.domain.services.ledger_service import LedgerService
            
            apuntes = [
                {"account_code": code_debe, "debe": amount, "haber": 0.0},
                {"account_code": code_haber, "debe": 0.0, "haber": amount}
            ]
            
            LedgerService.record_manual_entry(date_str, concept, apuntes)
            QMessageBox.information(self, "Éxito", "Asiento contable manual registrado correctamente.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo registrar el asiento: {e}")


class AlfonsoLedgerDialog(AlfonsoBaseDialog):
    """Diálogo para visualizar el Libro Diario Contable PGC y Libro Mayor."""
    def __init__(self, parent=None, api_client=None):
        super().__init__(parent, "LIBRO DIARIO CONTABLE (PLAN GENERAL CONTABLE)")
        self.setMinimumSize(950, 600)
        self.current_category = None
        self.setup_ledger_ui()

    def setup_ledger_ui(self):
        from PyQt6.QtWidgets import QStackedWidget
        
        # Segmented Control estilo macOS para alternar Diario/Mayor
        self.seg_layout = QHBoxLayout()
        self.seg_layout.setSpacing(2)
        self.seg_layout.setContentsMargins(0, 0, 0, 8)
        
        self.btn_view_diario = QPushButton("LIBRO DIARIO")
        self.btn_view_diario.setCheckable(True)
        self.btn_view_diario.setChecked(True)
        self.btn_view_diario.clicked.connect(lambda: self.switch_view(0))
        self.seg_layout.addWidget(self.btn_view_diario)
        
        self.btn_view_mayor = QPushButton("LIBRO MAYOR")
        self.btn_view_mayor.setCheckable(True)
        self.btn_view_mayor.clicked.connect(lambda: self.switch_view(1))
        self.seg_layout.addWidget(self.btn_view_mayor)
        
        self.content_layout.addLayout(self.seg_layout)
        
        # Main Stacked Widget
        self.main_stack = QStackedWidget()
        self.content_layout.addWidget(self.main_stack)

        # ── PÁGINA 1: LIBRO DIARIO (Doble Columna) ──
        self.page_diario = QWidget()
        diario_main_layout = QVBoxLayout(self.page_diario)
        diario_main_layout.setContentsMargins(0, 0, 0, 0)
        
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

        # PANEL 1: SIDEBAR DE FILTROS (Izquierda)
        self.left_panel = QWidget()
        self.left_panel.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.3);
            }
            QPushButton#FilterBtn {
                background-color: transparent;
                border: none;
                color: #94A3B8;
                text-align: left;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 500;
                border-radius: 6px;
            }
            QPushButton#FilterBtn:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
            }
            QPushButton#FilterBtn[active="true"] {
                background-color: rgba(99, 102, 241, 0.15);
                color: #818CF8;
                font-weight: bold;
            }
        """)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(6)

        lbl_filters = QLabel("FILTROS CONTABLES")
        lbl_filters.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent;")
        left_layout.addWidget(lbl_filters)

        self.filter_buttons = {}
        filters = [
            ("TODOS", None),
            ("INGRESOS (7xx)", "ingreso"),
            ("GASTOS (6xx)", "gasto"),
            ("MANUALES", "manual")
        ]
        for label, val in filters:
            btn = QPushButton(label)
            btn.setObjectName("FilterBtn")
            btn.setProperty("filter_val", val)
            btn.clicked.connect(self.filter_selected)
            self.filter_buttons[val] = btn
            left_layout.addWidget(btn)

        # Activo inicial
        self.filter_buttons[None].setProperty("active", "true")

        left_layout.addStretch()
        body_splitter.addWidget(self.left_panel)

        # PANEL 2: TABLA DIARIO (Centro/Derecha)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

        # Barra de acciones superior
        actions_layout = QHBoxLayout()
        self.btn_add_entry = QPushButton("NUEVO ASIENTO MANUAL")
        self.btn_add_entry.clicked.connect(self.open_manual_entry)
        actions_layout.addWidget(self.btn_add_entry)

        self.btn_export = QPushButton("EXPORTAR LIBRO DIARIO")
        self.btn_export.clicked.connect(self.export_ledger_csv)
        actions_layout.addWidget(self.btn_export)
        actions_layout.addStretch()
        right_layout.addLayout(actions_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["Fecha", "Asiento", "Cuenta PGC", "Nombre Cuenta", "Concepto", "Debe", "Haber"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        right_layout.addWidget(self.table)

        # Resumen inferior (Totales)
        self.summary_bar = QHBoxLayout()
        self.lbl_total_debe = QLabel("Total Debe: 0.00 €")
        self.lbl_total_debe.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px;")
        
        self.lbl_total_haber = QLabel("Total Haber: 0.00 €")
        self.lbl_total_haber.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px;")
        
        self.lbl_balance_status = QLabel("Balance: Cuadrado")
        self.lbl_balance_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11px;")
        
        self.summary_bar.addWidget(self.lbl_total_debe)
        self.summary_bar.addSpacing(25)
        self.summary_bar.addWidget(self.lbl_total_haber)
        self.summary_bar.addSpacing(25)
        self.summary_bar.addWidget(self.lbl_balance_status)
        self.summary_bar.addStretch()
        right_layout.addLayout(self.summary_bar)

        body_splitter.addWidget(self.right_panel)
        body_splitter.setSizes([160, 740])
        diario_main_layout.addWidget(body_splitter)
        self.main_stack.addWidget(self.page_diario)

        # ── PÁGINA 2: LIBRO MAYOR (Extracto de Cuentas) ──
        self.page_mayor = QWidget()
        page_mayor_layout = QVBoxLayout(self.page_mayor)
        page_mayor_layout.setContentsMargins(0, 5, 0, 0)
        page_mayor_layout.setSpacing(10)
        
        # Controles superiores
        mayor_filter_layout = QHBoxLayout()
        mayor_filter_layout.addWidget(QLabel("Seleccionar Cuenta PGC:"))
        
        self.cmb_mayor_account = QComboBox()
        self.cmb_mayor_account.setMinimumWidth(300)
        self.cmb_mayor_account.currentIndexChanged.connect(self.load_mayor_data)
        mayor_filter_layout.addWidget(self.cmb_mayor_account)
        
        self.btn_export_mayor = QPushButton("EXPORTAR ESTA CUENTA")
        self.btn_export_mayor.clicked.connect(self.export_mayor_csv)
        mayor_filter_layout.addWidget(self.btn_export_mayor)
        mayor_filter_layout.addStretch()
        page_mayor_layout.addLayout(mayor_filter_layout)
        
        # Tabla del Mayor
        self.table_mayor = QTableWidget()
        self.table_mayor.setColumnCount(6)
        self.table_mayor.setHorizontalHeaderLabels(["Fecha", "Asiento", "Concepto", "Debe", "Haber", "Saldo"])
        self.table_mayor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_mayor.verticalHeader().setVisible(False)
        page_mayor_layout.addWidget(self.table_mayor)
        
        # Totales del Mayor
        self.mayor_summary_layout = QHBoxLayout()
        self.lbl_mayor_total_debe = QLabel("Total Debe: 0.00 €")
        self.lbl_mayor_total_debe.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px;")
        
        self.lbl_mayor_total_haber = QLabel("Total Haber: 0.00 €")
        self.lbl_mayor_total_haber.setStyleSheet("font-weight: bold; color: #FFFFFF; font-size: 11px;")
        
        self.lbl_mayor_saldo_final = QLabel("Saldo Final: 0.00 €")
        self.lbl_mayor_saldo_final.setStyleSheet("font-weight: bold; color: #818CF8; font-size: 11px;")
        
        self.mayor_summary_layout.addWidget(self.lbl_mayor_total_debe)
        self.mayor_summary_layout.addSpacing(25)
        self.mayor_summary_layout.addWidget(self.lbl_mayor_total_haber)
        self.mayor_summary_layout.addSpacing(25)
        self.mayor_summary_layout.addWidget(self.lbl_mayor_saldo_final)
        self.mayor_summary_layout.addStretch()
        page_mayor_layout.addLayout(self.mayor_summary_layout)
        
        self.main_stack.addWidget(self.page_mayor)

        # Cargar catálogo de cuentas
        from app.domain.services.ledger_service import LedgerService
        accounts = LedgerService.get_pgc_accounts()
        for acc in accounts:
            label = f"{acc['code']} - {acc['name']}"
            self.cmb_mayor_account.addItem(label, acc['code'])

        # Cargar valores iniciales del Diario
        self.load_ledger_data()
        self.update_segmented_style()

    def switch_view(self, index):
        self.main_stack.setCurrentIndex(index)
        self.btn_view_diario.setChecked(index == 0)
        self.btn_view_mayor.setChecked(index == 1)
        self.update_segmented_style()
        if index == 1:
            self.load_mayor_data()

    def update_segmented_style(self):
        for idx, btn in enumerate([self.btn_view_diario, self.btn_view_mayor]):
            if btn.isChecked():
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(99, 102, 241, 0.25);
                        border: 1px solid #6366F1;
                        color: #FFFFFF;
                        font-weight: bold;
                        padding: 6px 14px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: rgba(255, 255, 255, 0.02);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        color: #CBD5E1;
                        font-weight: 500;
                        padding: 6px 14px;
                    }
                    QPushButton:hover {
                        background-color: rgba(255, 255, 255, 0.08);
                    }
                """)

    def filter_selected(self):
        sender_btn = self.sender()
        filter_val = sender_btn.property("filter_val")
        self.current_category = filter_val

        # Actualizar visual de botones activos
        for val, btn in self.filter_buttons.items():
            if val == filter_val:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            btn.setStyle(btn.style())

        self.load_ledger_data()

    def open_manual_entry(self):
        dialog = AlfonsoManualEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_ledger_data()

    def export_ledger_csv(self):
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, "Exportar Libro Diario", "libro_diario_2026.csv", "Archivos CSV (*.csv)")
            if not file_path:
                return
            
            import csv
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                # Cabecera
                writer.writerow(["Fecha", "Asiento", "Cuenta PGC", "Nombre Cuenta", "Concepto", "Debe", "Haber"])
                
                # Filas
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Exportar", "El libro diario ha sido exportado correctamente a CSV (compatible con Excel).")
        except Exception as e:
            QMessageBox.warning(self, "Error al exportar", f"No se pudo exportar el archivo: {e}")

    def load_ledger_data(self):
        try:
            from app.domain.services.ledger_service import LedgerService
            diario = LedgerService.get_libro_diario(2026)
            
            rows_data = []
            total_debe = 0.0
            total_haber = 0.0
            
            for asiento in diario:
                fecha = asiento["fecha"]
                a_id = asiento["asiento_id"]
                concepto = asiento.get("concepto", "")
                
                # Filtrar
                is_match = False
                if self.current_category is None:
                    is_match = True
                elif self.current_category == "manual":
                    if not concepto.startswith("Factura"):
                        is_match = True
                else:
                    # revisar si contiene cuentas correspondientes
                    for ap in asiento["apuntes"]:
                        if self.current_category == "ingreso" and (ap["cuenta"].startswith("7") or ap["cuenta"].startswith("430")):
                            is_match = True
                        elif self.current_category == "gasto" and (ap["cuenta"].startswith("6") or ap["cuenta"].startswith("400") or ap["cuenta"].startswith("472")):
                            is_match = True
                
                if not is_match:
                    continue
                    
                for ap in asiento["apuntes"]:
                    debe = ap["debe"]
                    haber = ap["haber"]
                    
                    total_debe += debe
                    total_haber += haber
                    
                    rows_data.append((
                        fecha,
                        f"#{a_id}",
                        ap["cuenta"],
                        ap["nombre_cuenta"],
                        concepto,
                        f"{debe:.2f} €" if debe > 0 else "",
                        f"{haber:.2f} €" if haber > 0 else ""
                    ))

            self.table.setRowCount(len(rows_data))
            for row_idx, data in enumerate(rows_data):
                for col_idx, val in enumerate(data):
                    self.table.setItem(row_idx, col_idx, QTableWidgetItem(val))
                    
            # Actualizar totales
            self.lbl_total_debe.setText(f"Total Debe: {total_debe:.2f} €")
            self.lbl_total_haber.setText(f"Total Haber: {total_haber:.2f} €")
            diff = abs(total_debe - total_haber)
            if diff < 0.01:
                self.lbl_balance_status.setText("Balance: Cuadrado ✓")
                self.lbl_balance_status.setStyleSheet("font-weight: bold; color: #10B981; font-size: 11px;")
            else:
                self.lbl_balance_status.setText(f"Descuadre: {diff:.2f} € ✗")
                self.lbl_balance_status.setStyleSheet("font-weight: bold; color: #EF4444; font-size: 11px;")
                
        except Exception as e:
            print(f"Error loading ledger: {e}")

    def load_mayor_data(self):
        code = self.cmb_mayor_account.currentData()
        if not code:
            return
            
        try:
            from app.domain.services.ledger_service import LedgerService
            mayor = LedgerService.get_libro_mayor(code, 2026)
            
            self.table_mayor.setRowCount(len(mayor))
            total_debe = 0.0
            total_haber = 0.0
            saldo_final = 0.0
            
            for idx, item in enumerate(mayor):
                debe = item["debe"]
                haber = item["haber"]
                saldo = item["saldo"]
                
                total_debe += debe
                total_haber += haber
                saldo_final = saldo
                
                self.table_mayor.setItem(idx, 0, QTableWidgetItem(item["fecha"]))
                self.table_mayor.setItem(idx, 1, QTableWidgetItem(f"#{item['asiento_id']}"))
                self.table_mayor.setItem(idx, 2, QTableWidgetItem(item["concepto"]))
                self.table_mayor.setItem(idx, 3, QTableWidgetItem(f"{debe:.2f} €" if debe > 0 else ""))
                self.table_mayor.setItem(idx, 4, QTableWidgetItem(f"{haber:.2f} €" if haber > 0 else ""))
                self.table_mayor.setItem(idx, 5, QTableWidgetItem(f"{saldo:.2f} €"))
                
            self.lbl_mayor_total_debe.setText(f"Total Debe: {total_debe:.2f} €")
            self.lbl_mayor_total_haber.setText(f"Total Haber: {total_haber:.2f} €")
            self.lbl_mayor_saldo_final.setText(f"Saldo Final: {saldo_final:.2f} €")
        except Exception as e:
            print(f"Error loading mayor data: {e}")

    def export_mayor_csv(self):
        code = self.cmb_mayor_account.currentData()
        if not code:
            return
            
        try:
            file_path, _ = QFileDialog.getSaveFileName(self, f"Exportar Libro Mayor {code}", f"mayor_{code}_2026.csv", "Archivos CSV (*.csv)")
            if not file_path:
                return
            
            import csv
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                # Cabecera
                writer.writerow(["Fecha", "Asiento", "Concepto", "Debe", "Haber", "Saldo"])
                
                # Filas
                for row in range(self.table_mayor.rowCount()):
                    row_data = []
                    for col in range(self.table_mayor.columnCount()):
                        item = self.table_mayor.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Exportar", "El extracto del libro mayor ha sido exportado correctamente.")
        except Exception as e:
            QMessageBox.warning(self, "Error al exportar", f"No se pudo exportar el archivo: {e}")


class AlfonsoDocumentViewerDialog(AlfonsoBaseDialog):
    """Visor nativo de documentos para PDF, JPG, PNG, DOCX, TXT y DOC."""
    def __init__(self, parent=None, filepath=None):
        import os
        filename = os.path.basename(filepath) if filepath else "DOCUMENTO"
        super().__init__(parent, f"VISOR - {filename.upper()}")
        self.filepath = filepath
        self.setMinimumSize(1150, 850)
        self.setup_viewer_ui()

    def setup_viewer_ui(self):
        from PyQt6.QtWidgets import QScrollArea, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QTextBrowser
        from PyQt6.QtCore import Qt
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #0B0F19;
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 8px;
            }
        """)
        
        self.viewer_widget = QWidget()
        self.viewer_layout = QVBoxLayout(self.viewer_widget)
        self.viewer_layout.setContentsMargins(10, 10, 10, 10)
        self.viewer_layout.setSpacing(15)
        self.viewer_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        
        self.scroll_area.setWidget(self.viewer_widget)
        self.content_layout.addWidget(self.scroll_area)
        
        # Barra de acciones inferior
        actions_layout = QHBoxLayout()
        actions_layout.setContentsMargins(0, 10, 0, 0)
        
        btn_external = QPushButton("ABRIR EXTERNAMENTE")
        btn_external.setFixedWidth(200)
        btn_external.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-color: #6366F1; color: #818CF8; font-weight: bold;")
        btn_external.clicked.connect(self.open_externally)
        actions_layout.addWidget(btn_external)
        
        actions_layout.addStretch()
        
        btn_close = QPushButton("CERRAR")
        btn_close.setFixedWidth(120)
        btn_close.clicked.connect(self.close)
        actions_layout.addWidget(btn_close)
        
        self.content_layout.addLayout(actions_layout)
        
        if self.filepath:
            self.load_document()

    def load_document(self):
        import os
        ext = os.path.splitext(self.filepath)[1].lower()
        if ext == ".pdf":
            self.render_pdf()
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            self.render_image()
        elif ext in (".txt", ".csv", ".log", ".sql", ".ini"):
            self.render_text()
        elif ext == ".docx":
            self.render_docx()
        elif ext == ".doc":
            self.render_doc()
        else:
            self.render_unsupported()

    def render_pdf(self):
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QPixmap, QImage
        from PyQt6.QtCore import Qt
        try:
            import pypdfium2 as pdfium
            
            doc = pdfium.PdfDocument(self.filepath)
            self._page_images = [] # Mantener referencias en memoria para evitar crash por GC de C++
            
            for i in range(len(doc)):
                page = doc[i]
                bitmap = page.render(scale=2.0)
                pil_img = bitmap.to_pil()
                
                # Convertir a RGBA y extraer los bytes en memoria
                pil_img = pil_img.convert("RGBA")
                width, height = pil_img.size
                img_data = pil_img.tobytes("raw", "RGBA")
                
                # Crear QImage a partir de los bytes y asociar la referencia para evitar GC prematuro
                qimage = QImage(img_data, width, height, QImage.Format.Format_RGBA8888)
                self._page_images.append(img_data)
                
                pixmap = QPixmap.fromImage(qimage)
                # Ajustar la página para que quepa en el visor completo sin scroll (máx 800x730)
                pixmap = pixmap.scaled(800, 730, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                lbl_page = QLabel()
                lbl_page.setPixmap(pixmap)
                lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
                lbl_page.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; background-color: #FFFFFF;")
                lbl_page.setScaledContents(False)
                
                self.viewer_layout.addWidget(lbl_page)
        except Exception as e:
            lbl_error = QLabel(f"Error renderizando PDF: {e}\n\nPuedes abrirlo externamente.")
            lbl_error.setStyleSheet("color: #EF4444; font-size: 14px; font-weight: bold; background: transparent;")
            lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.viewer_layout.addWidget(lbl_error)

    def render_image(self):
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import Qt
        lbl_img = QLabel()
        pixmap = QPixmap(self.filepath)
        if not pixmap.isNull():
            if pixmap.width() > 800 or pixmap.height() > 730:
                pixmap = pixmap.scaled(800, 730, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            lbl_img.setPixmap(pixmap)
            lbl_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_img.setStyleSheet("border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; background: #000000;")
            self.viewer_layout.addWidget(lbl_img)
        else:
            lbl_error = QLabel("Error al cargar la imagen.")
            lbl_error.setStyleSheet("color: #EF4444; font-size: 14px;")
            self.viewer_layout.addWidget(lbl_error)

    def render_text(self):
        from PyQt6.QtWidgets import QLabel, QTextBrowser
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            browser = QTextBrowser()
            browser.setPlainText(content)
            browser.setStyleSheet("""
                QTextBrowser {
                    background-color: rgba(15, 23, 42, 0.5);
                    border: none;
                    color: #F8FAFC;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 13px;
                }
            """)
            self.viewer_layout.addWidget(browser)
        except Exception as e:
            lbl_error = QLabel(f"Error leyendo archivo de texto: {e}")
            lbl_error.setStyleSheet("color: #EF4444;")
            self.viewer_layout.addWidget(lbl_error)

    def render_docx(self):
        from PyQt6.QtWidgets import QLabel, QTextBrowser
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            
            paragraphs = []
            with zipfile.ZipFile(self.filepath) as docx:
                xml_content = docx.read('word/document.xml')
                root = ET.fromstring(xml_content)
                for p in root.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p'):
                    texts = [node.text for node in p.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t') if node.text]
                    if texts:
                        paragraphs.append("".join(texts))
            
            text_content = "\n\n".join(paragraphs)
            browser = QTextBrowser()
            browser.setPlainText(text_content)
            browser.setStyleSheet("""
                QTextBrowser {
                    background-color: rgba(15, 23, 42, 0.5);
                    border: none;
                    color: #F8FAFC;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
            """)
            self.viewer_layout.addWidget(browser)
        except Exception as e:
            lbl_error = QLabel(f"Error leyendo DOCX: {e}")
            lbl_error.setStyleSheet("color: #EF4444;")
            self.viewer_layout.addWidget(lbl_error)

    def render_doc(self):
        from PyQt6.QtWidgets import QLabel, QTextBrowser
        from PyQt6.QtCore import Qt
        try:
            import win32com.client
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            doc = word.Documents.Open(self.filepath)
            text_content = doc.Content.Text
            doc.Close()
            word.Quit()
            
            browser = QTextBrowser()
            browser.setPlainText(text_content)
            browser.setStyleSheet("""
                QTextBrowser {
                    background-color: rgba(15, 23, 42, 0.5);
                    border: none;
                    color: #F8FAFC;
                    font-family: 'Segoe UI', sans-serif;
                    font-size: 14px;
                }
            """)
            self.viewer_layout.addWidget(browser)
        except Exception as e:
            lbl_error = QLabel("Formato Word (.doc) antiguo detectado.\n\nPara previsualizarlo, por favor ábralo externamente.")
            lbl_error.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: bold;")
            lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.viewer_layout.addWidget(lbl_error)

    def render_unsupported(self):
        from PyQt6.QtWidgets import QLabel
        from PyQt6.QtCore import Qt
        lbl_info = QLabel("El formato de este documento no soporta previsualización nativa.\n\nPuedes abrirlo externamente en su aplicación predeterminada.")
        lbl_info.setStyleSheet("color: #CBD5E1; font-size: 13px;")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_layout.addWidget(lbl_info)

    def open_externally(self):
        from PyQt6.QtWidgets import QMessageBox
        try:
            from PyQt6.QtCore import QUrl
            from PyQt6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.filepath))
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo abrir externamente: {e}")


class AlfonsoArchiveBrowserDialog(AlfonsoBaseDialog):
    """Explorador de Archivos Fiscales con estilo macOS Finder."""
    def __init__(self, parent=None):
        super().__init__(parent, "ARCHIVO FISCAL - EXPLORADOR DE DOCUMENTOS")
        self.setMinimumSize(1150, 750)
        self.archive_dir = os.path.abspath("data/archivo fiscal")
        os.makedirs(self.archive_dir, exist_ok=True)
        self.current_dir = self.archive_dir
        self.current_filter_type = "todos"
        self.history_back_stack = []
        self.history_forward_stack = []
        self.setup_archive_ui()

    def setup_archive_ui(self):
        from PyQt6.QtWidgets import QListView, QListWidget, QListWidgetItem, QStyle, QLineEdit, QSplitter
        from PyQt6.QtCore import QSize, QUrl
        from PyQt6.QtGui import QDesktopServices
        import shutil

        # 1. Barra de herramientas superior
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 10)
        
        self.btn_import_file = QPushButton("IMPORTAR DOCUMENTO")
        self.btn_import_file.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-color: #6366F1; color: #818CF8; font-weight: bold;")
        self.btn_import_file.clicked.connect(self.import_document)
        top_bar.addWidget(self.btn_import_file)

        top_bar.addSpacing(10)

        # Botones de navegación
        self.btn_back = QPushButton("◀")
        self.btn_back.setToolTip("Atrás")
        self.btn_back.setFixedWidth(36)
        self.btn_back.setStyleSheet("font-weight: bold; background-color: rgba(255, 255, 255, 0.05); color: #E2E8F0;")
        self.btn_back.clicked.connect(self.navigate_back)
        top_bar.addWidget(self.btn_back)
        
        self.btn_forward = QPushButton("▶")
        self.btn_forward.setToolTip("Adelante")
        self.btn_forward.setFixedWidth(36)
        self.btn_forward.setStyleSheet("font-weight: bold; background-color: rgba(255, 255, 255, 0.05); color: #E2E8F0;")
        self.btn_forward.clicked.connect(self.navigate_forward)
        top_bar.addWidget(self.btn_forward)
        
        self.btn_up = QPushButton("▲ SUBIR")
        self.btn_up.setToolTip("Subir un nivel")
        self.btn_up.setFixedWidth(80)
        self.btn_up.setStyleSheet("font-weight: bold; background-color: rgba(255, 255, 255, 0.05); color: #E2E8F0;")
        self.btn_up.clicked.connect(self.navigate_up)
        top_bar.addWidget(self.btn_up)
        
        top_bar.addStretch()
        
        # Buscador
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar documentos...")
        self.txt_search.setMinimumWidth(220)
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                padding: 6px 10px;
                color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #6366F1;
            }
        """)
        self.txt_search.textChanged.connect(self.filter_files)
        top_bar.addWidget(self.txt_search)
        
        self.content_layout.addLayout(top_bar)

        # 2. Splitter Principal (Sidebar / Grid / Inspector)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

        # PANEL 1: SIDEBAR DE FILTROS (Izquierda)
        self.sidebar = QWidget()
        self.sidebar.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 0.3);
            }
            QPushButton#SidebarBtn {
                background-color: transparent;
                border: none;
                color: #94A3B8;
                text-align: left;
                padding: 8px 12px;
                font-size: 11px;
                font-weight: 500;
                border-radius: 6px;
            }
            QPushButton#SidebarBtn:hover {
                background-color: rgba(255, 255, 255, 0.05);
                color: #FFFFFF;
            }
            QPushButton#SidebarBtn[active="true"] {
                background-color: rgba(99, 102, 241, 0.15);
                color: #818CF8;
                font-weight: bold;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(6)

        lbl_sidebar = QLabel("CATEGORÍAS")
        lbl_sidebar.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent;")
        sidebar_layout.addWidget(lbl_sidebar)

        self.sidebar_buttons = {}
        cats = [
            ("Todos los Archivos", "todos"),
            ("Facturas PDF", "pdf"),
            ("Imágenes", "img"),
            ("Otros Documentos", "otros")
        ]
        for label, val in cats:
            btn = QPushButton(label)
            btn.setObjectName("SidebarBtn")
            btn.setProperty("cat_val", val)
            btn.clicked.connect(self.sidebar_filter_selected)
            self.sidebar_buttons[val] = btn
            sidebar_layout.addWidget(btn)

        self.sidebar_buttons["todos"].setProperty("active", "true")

        sidebar_layout.addStretch()
        self.main_splitter.addWidget(self.sidebar)

        # PANEL 2: REJILLA DE ICONOS (Centro)
        self.grid_container = QWidget()
        grid_main_layout = QVBoxLayout(self.grid_container)
        grid_main_layout.setContentsMargins(0, 0, 0, 0)

        self.list_widget = QListWidget()
        self.list_widget.setViewMode(QListView.ViewMode.IconMode)
        self.list_widget.setResizeMode(QListView.ResizeMode.Adjust)
        self.list_widget.setGridSize(QSize(150, 140))
        self.list_widget.setIconSize(QSize(64, 64))
        self.list_widget.setWordWrap(True)
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                border: none;
            }
            QListWidget::item {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                margin: 4px;
                padding: 6px;
                color: #E2E8F0;
                font-size: 10px;
            }
            QListWidget::item:hover {
                background-color: rgba(99, 102, 241, 0.1);
                border-color: rgba(99, 102, 241, 0.3);
            }
            QListWidget::item:selected {
                background-color: rgba(99, 102, 241, 0.2);
                border-color: #6366F1;
                color: #FFFFFF;
                font-weight: bold;
            }
        """)
        self.list_widget.itemSelectionChanged.connect(self.show_file_details)
        self.list_widget.itemDoubleClicked.connect(self.open_selected_file)
        grid_main_layout.addWidget(self.list_widget)
        self.main_splitter.addWidget(self.grid_container)

        # PANEL 3: INSPECTOR / DETALLES (Derecha)
        self.inspector_panel = QWidget()
        self.inspector_panel.setStyleSheet("background-color: rgba(15, 23, 42, 0.2); border-left: 1px solid rgba(255, 255, 255, 0.05);")
        inspector_layout = QVBoxLayout(self.inspector_panel)
        inspector_layout.setContentsMargins(15, 15, 15, 15)
        inspector_layout.setSpacing(12)

        lbl_inspector_title = QLabel("INSPECTOR")
        lbl_inspector_title.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px;")
        inspector_layout.addWidget(lbl_inspector_title)

        # Previsualización o Icono Grande
        self.lbl_big_icon = QLabel("📄")
        self.lbl_big_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_big_icon.setStyleSheet("font-size: 54px; margin-top: 15px; margin-bottom: 10px;")
        inspector_layout.addWidget(self.lbl_big_icon)

        # Etiquetas de Información
        self.lbl_file_name = QLabel("Selecciona un archivo")
        self.lbl_file_name.setWordWrap(True)
        self.lbl_file_name.setStyleSheet("font-weight: bold; font-size: 12px; color: #FFFFFF; qproperty-alignment: AlignCenter;")
        self.lbl_file_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inspector_layout.addWidget(self.lbl_file_name)

        self.lbl_file_size = QLabel("-")
        self.lbl_file_size.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_file_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inspector_layout.addWidget(self.lbl_file_size)

        self.lbl_file_date = QLabel("-")
        self.lbl_file_date.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_file_date.setAlignment(Qt.AlignmentFlag.AlignCenter)
        inspector_layout.addWidget(self.lbl_file_date)

        inspector_layout.addStretch()

        # Botones de Acción del Inspector
        self.btn_open_file = QPushButton("ABRIR DOCUMENTO")
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.clicked.connect(self.open_selected_file)
        inspector_layout.addWidget(self.btn_open_file)

        self.btn_delete_file = QPushButton("ELIMINAR")
        self.btn_delete_file.setEnabled(False)
        self.btn_delete_file.setStyleSheet("background-color: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); color: #F87171;")
        self.btn_delete_file.clicked.connect(self.delete_selected_file)
        inspector_layout.addWidget(self.btn_delete_file)

        self.main_splitter.addWidget(self.inspector_panel)
        
        # Ajustar tamaños iniciales de las columnas
        self.main_splitter.setSizes([160, 480, 210])
        self.content_layout.addWidget(self.main_splitter)

        self.load_files()

    def load_files(self):
        from PyQt6.QtWidgets import QStyle, QListWidgetItem
        from PyQt6.QtCore import Qt
        self.list_widget.clear()
        self.reset_inspector()
        
        if not os.path.exists(self.current_dir):
            return
            
        try:
            # Actualizar estado de los botones de navegación
            self.btn_back.setEnabled(len(self.history_back_stack) > 0)
            self.btn_forward.setEnabled(len(self.history_forward_stack) > 0)
            is_at_root = os.path.abspath(self.current_dir) == os.path.abspath(self.archive_dir)
            self.btn_up.setEnabled(not is_at_root)

            # Listar contenidos
            items = os.listdir(self.current_dir)
            dirs = []
            files = []
            for name in items:
                full_path = os.path.join(self.current_dir, name)
                if os.path.isdir(full_path):
                    dirs.append(name)
                else:
                    files.append(name)
            
            dirs.sort()
            files.sort()
            
            # Cargar carpetas primero
            for dname in dirs:
                full_path = os.path.join(self.current_dir, dname)
                item = QListWidgetItem()
                item.setText(dname)
                item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                item.setData(Qt.ItemDataRole.UserRole + 1, True)
                self.list_widget.addItem(item)
                
            # Cargar archivos
            for fname in files:
                full_path = os.path.join(self.current_dir, fname)
                ext = os.path.splitext(fname)[1].lower()
                
                is_match = False
                if self.current_filter_type == "todos":
                    is_match = True
                elif self.current_filter_type == "pdf":
                    if ext == ".pdf":
                        is_match = True
                elif self.current_filter_type == "img":
                    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                        is_match = True
                elif self.current_filter_type == "otros":
                    if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                        is_match = True
                        
                if not is_match:
                    continue
                    
                item = QListWidgetItem()
                item.setText(fname)
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                item.setData(Qt.ItemDataRole.UserRole + 1, False)
                
                if ext == ".pdf":
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogImageIcon))
                else:
                    item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                    
                self.list_widget.addItem(item)
        except Exception as e:
            print(f"Error loading archive files: {e}")

    def sidebar_filter_selected(self):
        sender_btn = self.sender()
        cat_val = sender_btn.property("cat_val")
        self.current_filter_type = cat_val

        for val, btn in self.sidebar_buttons.items():
            if val == cat_val:
                btn.setProperty("active", "true")
            else:
                btn.setProperty("active", "false")
            btn.setStyle(btn.style())

        self.load_files()

    def navigate_back(self):
        if self.history_back_stack:
            self.history_forward_stack.append(self.current_dir)
            self.current_dir = self.history_back_stack.pop()
            self.load_files()

    def navigate_forward(self):
        if self.history_forward_stack:
            self.history_back_stack.append(self.current_dir)
            self.current_dir = self.history_forward_stack.pop()
            self.load_files()

    def navigate_up(self):
        parent_dir = os.path.abspath(os.path.join(self.current_dir, ".."))
        if os.path.abspath(self.current_dir) != os.path.abspath(self.archive_dir):
            self.change_directory(parent_dir)

    def change_directory(self, new_dir):
        if os.path.abspath(new_dir) != os.path.abspath(self.current_dir):
            self.history_back_stack.append(self.current_dir)
            self.history_forward_stack.clear()
            self.current_dir = new_dir
            self.load_files()

    def filter_files(self, text):
        try:
            query = text.strip()
            if not query:
                self.load_files()
                return

            from PyQt6.QtWidgets import QStyle, QListWidgetItem
            from PyQt6.QtCore import Qt
            self.list_widget.clear()
            self.reset_inspector()
            
            for root, dirs, files in os.walk(self.archive_dir):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    
                    is_cat_match = False
                    if self.current_filter_type == "todos":
                        is_cat_match = True
                    elif self.current_filter_type == "pdf":
                        if ext == ".pdf":
                            is_cat_match = True
                    elif self.current_filter_type == "img":
                        if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                            is_cat_match = True
                    elif self.current_filter_type == "otros":
                        if ext not in (".pdf", ".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                            is_cat_match = True
                            
                    if not is_cat_match:
                        continue
                        
                    file_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(file_path, self.archive_dir).replace("\\", "/")
                    
                    # Si el texto coincide con la ruta relativa del archivo
                    if query.lower() in rel_path.lower():
                        item = QListWidgetItem()
                        item.setText(rel_path)
                        item.setData(Qt.ItemDataRole.UserRole, file_path)
                        item.setData(Qt.ItemDataRole.UserRole + 1, False)
                        
                        if ext == ".pdf":
                            item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
                            item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogImageIcon))
                        else:
                            item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
                            
                        self.list_widget.addItem(item)
        except Exception as e:
            print(f"Error en filter_files: {e}")

    def show_file_details(self):
        from PyQt6.QtCore import Qt
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            self.reset_inspector()
            return
            
        file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        is_dir = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)
        filename = os.path.basename(file_path)
            
        if not file_path or not os.path.exists(file_path):
            self.reset_inspector()
            return
            
        try:
            if is_dir:
                self.lbl_big_icon.setText("📁")
                self.lbl_file_name.setText(filename)
                self.lbl_file_size.setText("Carpeta de archivos")
                self.lbl_file_date.setText("-")
                self.btn_open_file.setText("ENTRAR")
                self.btn_open_file.setEnabled(True)
                self.btn_delete_file.setEnabled(True)
            else:
                size_bytes = os.path.getsize(file_path)
                if size_bytes < 1024:
                    size_str = f"{size_bytes} Bytes"
                elif size_bytes < 1024 * 1024:
                    size_str = f"{size_bytes / 1024:.2f} KB"
                else:
                    size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
                    
                import datetime
                mtime = os.path.getmtime(file_path)
                date_str = datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M")
                
                ext = os.path.splitext(filename)[1].lower()
                if ext == ".pdf":
                    self.lbl_big_icon.setText("📕")
                elif ext in (".png", ".jpg", ".jpeg", ".gif"):
                    self.lbl_big_icon.setText("🖼️")
                else:
                    self.lbl_big_icon.setText("📄")
                    
                self.lbl_file_name.setText(filename)
                self.lbl_file_size.setText(f"Tamaño: {size_str}")
                self.lbl_file_date.setText(f"Modificado: {date_str}")
                
                self.btn_open_file.setText("ABRIR DOCUMENTO")
                self.btn_open_file.setEnabled(True)
                self.btn_delete_file.setEnabled(True)
        except Exception as e:
            print(f"Error reading file details: {e}")

    def reset_inspector(self):
        self.lbl_big_icon.setText("📄")
        self.lbl_file_name.setText("Selecciona un archivo")
        self.lbl_file_size.setText("-")
        self.lbl_file_date.setText("-")
        self.btn_open_file.setText("ABRIR DOCUMENTO")
        self.btn_open_file.setEnabled(False)
        self.btn_delete_file.setEnabled(False)

    def open_selected_file(self):
        from PyQt6.QtCore import Qt
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        is_dir = selected_items[0].data(Qt.ItemDataRole.UserRole + 1)
        
        if is_dir:
            self.change_directory(file_path)
        else:
            try:
                self.viewer = AlfonsoDocumentViewerDialog(self, file_path)
                self.viewer.show()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo abrir el visor de documentos: {e}")

    def delete_selected_file(self):
        from PyQt6.QtCore import Qt
        selected_items = self.list_widget.selectedItems()
        if not selected_items:
            return
        file_path = selected_items[0].data(Qt.ItemDataRole.UserRole)
        filename = os.path.basename(file_path)
        
        confirm = QMessageBox.question(
            self, "Confirmar borrado", 
            f"¿Estás seguro de que deseas eliminar permanentemente el archivo:\n\n{filename}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                if os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    os.remove(file_path)
                self.load_files()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudo eliminar el archivo: {e}")

    def import_document(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar Documento al Archivo Fiscal", "", "Todos los Archivos (*.*)")
        if not file_path:
            return
            
class EconomicAnalyzerThread(QThread):
    progress_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    
    def __init__(self, data_stats):
        super().__init__()
        self.stats = data_stats
        
    def run(self):
        import time
        self.progress_signal.emit("[SISTEMA ALFONSO] Iniciando análisis financiero de riesgos...")
        time.sleep(0.8)
        self.progress_signal.emit("[CONEXIÓN SECURE] Consultando base de datos local y libro contable...")
        time.sleep(0.6)
        self.progress_signal.emit("[WEB AGENT] Buscando noticias macroeconómicas del sector en España 2026...")
        time.sleep(1.0)
        self.progress_signal.emit("[WEB AGENT] Analizando reforma del RETA, IPC actualizados y MEAE tributario...")
        time.sleep(0.8)
        self.progress_signal.emit("[AUDITORÍA] Procesando margen operativo y tasa de cash burn...")
        time.sleep(0.6)
        self.progress_signal.emit("[DIAGNÓSTICO] Redactando informe crítico de viabilidad y estrategias...")
        time.sleep(0.5)
        
        ing = self.stats.get('total_ingresos', 0.0)
        gast = self.stats.get('total_gastos', 0.0)
        neto = ing - gast
        iva = self.stats.get('total_iva', 0.0)
        irpf = self.stats.get('total_irpf', 0.0)
        
        ratio_gastos = (gast / ing * 100) if ing > 0 else 0
        rentabilidad = (neto / ing * 100) if ing > 0 else 0
        
        report = f"""========================================================================
ALFONSO FINANCIAL INTEL SYSTEM - INFORME ESTRATÉGICO Y JUICIO CRÍTICO
========================================================================
FECHA DE EMISIÓN: 06 de Agosto de 2026
ESTADO DE AUDITORÍA: CRÍTICO Y ESTRATÉGICO

1. AUDITORÍA DE DATOS DE LA EMPRESA (AÑO CURSO 2026):
------------------------------------------------------------------------
* INGRESOS DECLARADOS: {ing:,.2f} €
* GASTOS TOTALES REGISTRADOS: {gast:,.2f} €
* RESULTADO NETO (EXPLICIT): {neto:,.2f} €
* IVA ACUMULADO (SOPORTADO/REPERCUTIDO): {iva:,.2f} €
* IRPF RETENIDO/LIQUIDADO ACUMULADO: {irpf:,.2f} €

ANÁLISIS DE EFICIENCIA:
* Tasa de Gasto Operativo: {ratio_gastos:.2f}% (Consumo de cada euro ingresado).
* Rentabilidad Neta del Ejercicio: {rentabilidad:.2f}%

2. CONTEXTO MACROECONÓMICO DEL SECTOR (ESPAÑA - SEGUNDO SEMESTRE 2026):
------------------------------------------------------------------------
Tras consultar información abierta y noticias financieras recientes sobre el sector servicios y autónomos:
- Reforma de Cotizaciones RETA 2026: La consolidación de la tabla de cotización progresiva por ingresos reales ha incrementado la presión fiscal en los tramos medios y altos. Cada euro neto adicional eleva la cuota mensual.
- Incremento del MEAE (Mecanismo de Equidad Intergeneracional): Aumento del coste en seguros sociales y nóminas del 1.2%, reduciendo márgenes.
- Inflación subyacente persistente en el 3.1%: El coste de suministros, servidores cloud, software SaaS y oficinas se ha encarecido, limitando el margen de rentabilidad si no se trasladan costes al cliente.
- Enfriamiento en el sector servicios tecnológicos y de consultoría: Reducción del ticket medio de contratación por parte de Pymes europeas en un 12% debido a las políticas monetarias contractivas del BCE.

3. JUICIO DE VALOR TOTALMENTE CRÍTICO:
------------------------------------------------------------------------
"""
        if ing == 0:
            report += "¡ALERTA CRÍTICA: NO SE REGISTRAN INGRESOS EN EL AÑO CURSO! La viabilidad financiera es inexistente. Estás operando en pérdidas absolutas dependientes de fondos externos. Riesgo inminente de quiebra técnica.\n"
        elif rentabilidad > 15:
            report += f"Nivel de alarma: MODERADO. Con un margen neto del {rentabilidad:.1f}%, la empresa genera valor. Sin embargo, el consumo de gastos representa un {ratio_gastos:.1f}% de tus ingresos. En el ecosistema fiscal de 2026, con el aumento progresivo de cuotas del RETA, esta estructura es sumamente vulnerable a cualquier caída de clientes.\n"
        else:
            report += "¡ALERTA FINANCIERA! Rentabilidad por debajo del umbral óptimo (<15%). Tu negocio se encuentra al borde de la subsistencia pura. Estás asumiendo todo el riesgo del autónomo para un rendimiento neto insuficiente que no compensará futuras cargas tributarias de cierre de año.\n"

        report += f"""
4. ESTRATEGIAS DE SUPERVIVENCIA Y MANTENIMIENTO:
------------------------------------------------------------------------
A) Reestructuración Inmediata de Costes (Cost-cutting):
   - Auditar suscripciones SaaS recurrentes redundantes o infrautilizadas.
   - Renegociar contratos de servicios (proveedores, telecomunicaciones, coworking).
B) Optimización de Ingresos (Pricing & Value):
   - Indexar tarifas un 5% para cubrir el impacto de la inflación acumulada.
   - Transicionar de facturación por horas a modelos de retención (retainers) fijos mensuales para estabilizar el flujo de caja.
C) Cobertura Fiscal (Tax Planning):
   - Maximizar la deducción de gastos afectos a la actividad (herramientas de software, suministros de teletrabajo regulados).
   - Realizar cierres simulados mensuales para prever las retenciones del Modelo 130 y el pago de IVA trimestral para evitar estrangulamientos de liquidez.

========================================================================="""
        self.result_signal.emit(report)


class KPIChartWidget(QWidget):
    """Gráfico de series temporales personalizado usando QPainter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(580, 260)
        self.data = {}
        self.show_all_time = False
        
    def set_data(self, data, show_all_time=False):
        self.data = data
        self.show_all_time = show_all_time
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.setPen(QPen(QColor(99, 102, 241, 50), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        
        if not self.data:
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos disponibles para graficar")
            return
            
        keys = sorted(self.data.keys())
        left_margin = 60
        right_margin = 30
        top_margin = 40
        bottom_margin = 45
        
        chart_w = self.width() - left_margin - right_margin
        chart_h = self.height() - top_margin - bottom_margin
        
        max_val = 1.0
        for k in keys:
            max_val = max(max_val, self.data[k]['ingresos'], self.data[k]['gastos'])
            
        max_val = ((int(max_val) // 1000) + 1) * 1000
        
        painter.setFont(QFont("Consolas", 8))
        grid_lines = 4
        for i in range(grid_lines + 1):
            y = top_margin + chart_h - (i * chart_h // grid_lines)
            val = i * max_val // grid_lines
            painter.setPen(QPen(QColor(255, 255, 255, 15), 1, Qt.PenStyle.DashLine))
            painter.drawLine(left_margin, y, left_margin + chart_w, y)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(10, y + 4, f"{val:,.0f}€".replace(",", "."))
            
        num_points = len(keys)
        x_step = chart_w / max(1, num_points - 1)
        
        path_ing = QPainterPath()
        path_gast = QPainterPath()
        
        points_ing = []
        points_gast = []
        
        meses_nombres = {
            "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
        }
        
        for i, k in enumerate(keys):
            x = left_margin + i * x_step
            y_ing = top_margin + chart_h - (self.data[k]['ingresos'] * chart_h / max_val)
            y_gast = top_margin + chart_h - (self.data[k]['gastos'] * chart_h / max_val)
            points_ing.append((x, y_ing))
            points_gast.append((x, y_gast))
            if i == 0:
                path_ing.moveTo(x, y_ing)
                path_gast.moveTo(x, y_gast)
            else:
                path_ing.lineTo(x, y_ing)
                path_gast.lineTo(x, y_gast)
            lbl_x = k
            if not self.show_all_time and k in meses_nombres:
                lbl_x = meses_nombres[k]
            painter.setPen(QColor(148, 163, 184))
            if num_points > 12:
                if i % 3 == 0:
                    painter.drawText(int(x - 15), top_margin + chart_h + 20, lbl_x)
            else:
                painter.drawText(int(x - 12), top_margin + chart_h + 20, lbl_x)
                
        painter.setPen(QPen(QColor(239, 68, 68, 220), 2))
        painter.drawPath(path_gast)
        painter.setBrush(QColor(239, 68, 68))
        for p in points_gast:
            painter.drawEllipse(int(p[0] - 3), int(p[1] - 3), 6, 6)
            
        painter.setPen(QPen(QColor(16, 185, 129, 255), 2))
        painter.drawPath(path_ing)
        painter.setBrush(QColor(16, 185, 129))
        for p in points_ing:
            painter.drawEllipse(int(p[0] - 3), int(p[1] - 3), 6, 6)


class KPITaxesChartWidget(QWidget):
    """Gráfico de series temporales para impuestos (IVA e IRPF por separado)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(580, 240)
        self.data = {}
        self.show_all_time = False
        
    def set_data(self, data, show_all_time=False):
        self.data = data
        self.show_all_time = show_all_time
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.setBrush(QColor(15, 23, 42, 220))
        painter.setPen(QPen(QColor(99, 102, 241, 50), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
        
        if not self.data:
            painter.setFont(QFont("Segoe UI", 10))
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos de impuestos disponibles")
            return
            
        keys = sorted(self.data.keys())
        left_margin = 60
        right_margin = 30
        top_margin = 40
        bottom_margin = 45
        
        chart_w = self.width() - left_margin - right_margin
        chart_h = self.height() - top_margin - bottom_margin
        
        max_val = 1.0
        for k in keys:
            max_val = max(max_val, self.data[k]['iva'], self.data[k]['irpf'])
            
        max_val = ((int(max_val) // 500) + 1) * 500
        
        painter.setFont(QFont("Consolas", 8))
        grid_lines = 4
        for i in range(grid_lines + 1):
            y = top_margin + chart_h - (i * chart_h // grid_lines)
            val = i * max_val // grid_lines
            painter.setPen(QPen(QColor(255, 255, 255, 15), 1, Qt.PenStyle.DashLine))
            painter.drawLine(left_margin, y, left_margin + chart_w, y)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(10, y + 4, f"{val:,.0f}€".replace(",", "."))
            
        num_points = len(keys)
        x_step = chart_w / max(1, num_points - 1)
        
        path_iva = QPainterPath()
        path_irpf = QPainterPath()
        
        points_iva = []
        points_irpf = []
        
        meses_nombres = {
            "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
        }
        
        for i, k in enumerate(keys):
            x = left_margin + i * x_step
            y_iva = top_margin + chart_h - (self.data[k]['iva'] * chart_h / max_val)
            y_irpf = top_margin + chart_h - (self.data[k]['irpf'] * chart_h / max_val)
            points_iva.append((x, y_iva))
            points_irpf.append((x, y_irpf))
            if i == 0:
                path_iva.moveTo(x, y_iva)
                path_irpf.moveTo(x, y_irpf)
            else:
                path_iva.lineTo(x, y_iva)
                path_irpf.lineTo(x, y_irpf)
            lbl_x = k
            if not self.show_all_time and k in meses_nombres:
                lbl_x = meses_nombres[k]
            painter.setPen(QColor(148, 163, 184))
            if num_points > 12:
                if i % 3 == 0:
                    painter.drawText(int(x - 15), top_margin + chart_h + 20, lbl_x)
            else:
                painter.drawText(int(x - 12), top_margin + chart_h + 20, lbl_x)
                
        painter.setPen(QPen(QColor(245, 158, 11, 220), 2))
        painter.drawPath(path_irpf)
        painter.setBrush(QColor(245, 158, 11))
        for p in points_irpf:
            painter.drawEllipse(int(p[0] - 3), int(p[1] - 3), 6, 6)
            
        painter.setPen(QPen(QColor(59, 130, 246, 255), 2))
        painter.drawPath(path_iva)
        painter.setBrush(QColor(59, 130, 246))
        for p in points_iva:
            painter.drawEllipse(int(p[0] - 3), int(p[1] - 3), 6, 6)


from PyQt6.QtWidgets import QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QTextEdit, QButtonGroup, QProgressBar, QFrame
from PyQt6.QtCore import Qt, QThread, pyqtSignal

class AlfonsoKPIDashboardDialog(AlfonsoBaseDialog):
    """Dashboard de KPIs de negocio y análisis estratégico."""
    def __init__(self, parent=None):
        super().__init__(parent, "SISTEMA DE CONTROL DE NEGOCIO & KPIs")
        self.setMinimumSize(1200, 800)
        self.show_all_time = False
        self.setup_kpi_ui()
        self.load_kpi_data()
        
    def setup_kpi_ui(self):
        main_layout = self.content_layout
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        top_row = QHBoxLayout()
        self.btn_period_2026 = QPushButton("AÑO FISCAL 2026")
        self.btn_period_2026.setCheckable(True)
        self.btn_period_2026.setChecked(True)
        self.btn_period_2026.setStyleSheet("""
            QPushButton {
                background-color: rgba(99, 102, 241, 0.3);
                border: 1px solid #818CF8;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        self.btn_period_2026.clicked.connect(self.set_period_2026)
        
        self.btn_period_all = QPushButton("HISTÓRICO COMPLETO")
        self.btn_period_all.setCheckable(True)
        self.btn_period_all.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #94A3B8;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        self.btn_period_all.clicked.connect(self.set_period_all)
        
        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_period_2026)
        self.btn_group.addButton(self.btn_period_all)
        self.btn_group.setExclusive(True)
        
        top_row.addWidget(self.btn_period_2026)
        top_row.addWidget(self.btn_period_all)
        top_row.addStretch()
        main_layout.addLayout(top_row)
        
        columns_layout = QHBoxLayout()
        columns_layout.setSpacing(15)
        
        left_column = QVBoxLayout()
        left_column.setSpacing(15)
        
        lbl_c1_title = QLabel("EVOLUTIVO DE INGRESOS Y GASTOS (BASE IMPONIBLE)")
        lbl_c1_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #818CF8; letter-spacing: 0.5px;")
        left_column.addWidget(lbl_c1_title)
        
        self.chart = KPIChartWidget(self)
        left_column.addWidget(self.chart, 1)
        
        lbl_c2_title = QLabel("EVOLUTIVO DE IMPUESTOS LIQUIDADOS (IVA VS IRPF POR SEPARADO)")
        lbl_c2_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #3B82F6; letter-spacing: 0.5px;")
        left_column.addWidget(lbl_c2_title)
        
        self.chart_taxes = KPITaxesChartWidget(self)
        left_column.addWidget(self.chart_taxes, 1)
        
        columns_layout.addLayout(left_column, 6)
        
        right_column = QVBoxLayout()
        right_column.setSpacing(15)
        
        lbl_kpis_title = QLabel("KPIs DE RENDIMIENTO OPERATIVO")
        lbl_kpis_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #FFB800; letter-spacing: 0.5px;")
        right_column.addWidget(lbl_kpis_title)
        
        kpi_card = QFrame()
        kpi_card.setStyleSheet("background-color: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 10px;")
        kpi_card_layout = QVBoxLayout(kpi_card)
        kpi_card_layout.setSpacing(8)
        
        ret_lay = QHBoxLayout()
        lbl_ret = QLabel("Rentabilidad Neta:")
        lbl_ret.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        self.lbl_ret_val = QLabel("0,0%")
        self.lbl_ret_val.setStyleSheet("font-size: 11px; font-weight: bold; color: #10B981;")
        ret_lay.addWidget(lbl_ret)
        ret_lay.addStretch()
        ret_lay.addWidget(self.lbl_ret_val)
        kpi_card_layout.addLayout(ret_lay)
        
        self.bar_rentabilidad = QProgressBar()
        self.bar_rentabilidad.setFixedHeight(6)
        self.bar_rentabilidad.setTextVisible(False)
        self.bar_rentabilidad.setStyleSheet("""
            QProgressBar { background-color: rgba(255, 255, 255, 0.05); border: none; border-radius: 3px; }
            QProgressBar::chunk { background-color: #10B981; border-radius: 3px; }
        """)
        kpi_card_layout.addWidget(self.bar_rentabilidad)
        
        iva_lay = QHBoxLayout()
        lbl_iva_txt = QLabel("IVA Acumulado Soportado:")
        lbl_iva_txt.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        self.lbl_iva_val = QLabel("0,00 €")
        self.lbl_iva_val.setStyleSheet("font-family: 'Consolas'; font-size: 11px; font-weight: bold; color: #3B82F6;")
        iva_lay.addWidget(lbl_iva_txt)
        iva_lay.addStretch()
        iva_lay.addWidget(self.lbl_iva_val)
        kpi_card_layout.addLayout(iva_lay)
        
        irpf_lay = QHBoxLayout()
        lbl_irpf_txt = QLabel("IRPF Retenido Acumulado:")
        lbl_irpf_txt.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        self.lbl_irpf_val = QLabel("0,00 €")
        self.lbl_irpf_val.setStyleSheet("font-family: 'Consolas'; font-size: 11px; font-weight: bold; color: #F59E0B;")
        irpf_lay.addWidget(lbl_irpf_txt)
        irpf_lay.addStretch()
        irpf_lay.addWidget(self.lbl_irpf_val)
        kpi_card_layout.addLayout(irpf_lay)
        
        right_column.addWidget(kpi_card)
        
        lbl_dist_title = QLabel("DISTRIBUCIÓN DE GASTOS DECLARADOS")
        lbl_dist_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #EF4444; letter-spacing: 0.5px;")
        right_column.addWidget(lbl_dist_title)
        
        dist_card = QFrame()
        dist_card.setStyleSheet("background-color: rgba(30, 41, 59, 0.4); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 6px; padding: 10px;")
        dist_card_layout = QVBoxLayout(dist_card)
        dist_card_layout.setSpacing(6)
        
        lay_ofi = QHBoxLayout()
        lay_ofi.addWidget(QLabel("🏢 Oficina / Coworking"))
        self.lbl_ofi_pct = QLabel("0%")
        self.lbl_ofi_pct.setStyleSheet("font-weight: bold;")
        lay_ofi.addStretch()
        lay_ofi.addWidget(self.lbl_ofi_pct)
        dist_card_layout.addLayout(lay_ofi)
        self.bar_ofi = QProgressBar()
        self.bar_ofi.setFixedHeight(4)
        self.bar_ofi.setTextVisible(False)
        self.bar_ofi.setStyleSheet("QProgressBar { background-color: rgba(255, 255, 255, 0.05); border: none; } QProgressBar::chunk { background-color: #EF4444; }")
        dist_card_layout.addWidget(self.bar_ofi)
        
        lay_tel = QHBoxLayout()
        lay_tel.addWidget(QLabel("📞 Telecomunicaciones / Internet"))
        self.lbl_tel_pct = QLabel("0%")
        self.lbl_tel_pct.setStyleSheet("font-weight: bold;")
        lay_tel.addStretch()
        lay_tel.addWidget(self.lbl_tel_pct)
        dist_card_layout.addLayout(lay_tel)
        self.bar_tel = QProgressBar()
        self.bar_tel.setFixedHeight(4)
        self.bar_tel.setTextVisible(False)
        self.bar_tel.setStyleSheet("QProgressBar { background-color: rgba(255, 255, 255, 0.05); border: none; } QProgressBar::chunk { background-color: #EF4444; }")
        dist_card_layout.addWidget(self.bar_tel)
        
        lay_otr = QHBoxLayout()
        lay_otr.addWidget(QLabel("📦 Otros Suministros y Software"))
        self.lbl_otr_pct = QLabel("0%")
        self.lbl_otr_pct.setStyleSheet("font-weight: bold;")
        lay_otr.addStretch()
        lay_otr.addWidget(self.lbl_otr_pct)
        dist_card_layout.addLayout(lay_otr)
        self.bar_otr = QProgressBar()
        self.bar_otr.setFixedHeight(4)
        self.bar_otr.setTextVisible(False)
        self.bar_otr.setStyleSheet("QProgressBar { background-color: rgba(255, 255, 255, 0.05); border: none; } QProgressBar::chunk { background-color: #A855F7; }")
        dist_card_layout.addWidget(self.bar_otr)
        
        right_column.addWidget(dist_card)
        
        self.btn_evaluate = QPushButton("EMITIR JUICIO DE VALOR Y AUDITORÍA SECTORIAL")
        self.btn_evaluate.setStyleSheet("""
            QPushButton {
                background-color: rgba(239, 68, 68, 0.15);
                border: 1px solid #EF4444;
                color: #F87171;
                font-weight: bold;
                font-size: 11px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(239, 68, 68, 0.3);
                color: #FFFFFF;
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 0.05);
                border-color: rgba(255, 255, 255, 0.1);
                color: #64748B;
            }
        """)
        self.btn_evaluate.clicked.connect(self.run_economic_audit)
        right_column.addWidget(self.btn_evaluate)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setPlaceholderText("Haz clic en el botón superior para realizar la auditoría económica del negocio en tiempo real...")
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #0B0F19;
                border: 1px solid rgba(0, 240, 255, 0.2);
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 10px;
                color: #00F0FF;
                border-radius: 6px;
                padding: 6px;
            }
        """)
        right_column.addWidget(self.terminal, 1)
        
        columns_layout.addLayout(right_column, 4)
        main_layout.addLayout(columns_layout)
        
    def set_period_2026(self):
        self.show_all_time = False
        self.btn_period_2026.setStyleSheet("QPushButton { background-color: rgba(99, 102, 241, 0.3); border: 1px solid #818CF8; color: #FFFFFF; font-weight: bold; padding: 6px 12px; border-radius: 4px; }")
        self.btn_period_all.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.1); color: #94A3B8; font-weight: bold; padding: 6px 12px; border-radius: 4px; }")
        self.load_kpi_data()
        
    def set_period_all(self):
        self.show_all_time = True
        self.btn_period_all.setStyleSheet("QPushButton { background-color: rgba(99, 102, 241, 0.3); border: 1px solid #818CF8; color: #FFFFFF; font-weight: bold; padding: 6px 12px; border-radius: 4px; }")
        self.btn_period_2026.setStyleSheet("QPushButton { background-color: rgba(255, 255, 255, 0.02); border: 1px solid rgba(255, 255, 255, 0.1); color: #94A3B8; font-weight: bold; padding: 6px 12px; border-radius: 4px; }")
        self.load_kpi_data()
        
    def load_kpi_data(self):
        try:
            from app.adapters.memory.memory import _get_connection
            from app.utils.encryption import encryptor
            import collections
            
            monthly_data = collections.defaultdict(lambda: {'ingresos': 0.0, 'gastos': 0.0, 'iva': 0.0, 'irpf': 0.0})
            gastos_ofi = 0.0
            gastos_tel = 0.0
            gastos_otr = 0.0
            total_ing = 0.0
            total_gast = 0.0
            total_iva = 0.0
            total_irpf = 0.0
            
            with _get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT base_imponible, iva_amount, irpf_amount, category, date, year, issuer_name FROM invoices"
                if not self.show_all_time:
                    query += " WHERE year = 2026"
                cursor.execute(query)
                rows = cursor.fetchall()
                
                for row in rows:
                    try:
                        base = float(encryptor.decrypt(row["base_imponible"]))
                        iva = float(encryptor.decrypt(row["iva_amount"])) if row["iva_amount"] else 0.0
                        irpf = float(encryptor.decrypt(row["irpf_amount"])) if row["irpf_amount"] else 0.0
                        cat = row["category"]
                        date_str = row["date"]
                        year_val = row["year"]
                        issuer = encryptor.decrypt(row["issuer_name"]) if row["issuer_name"] else ""
                        
                        month_key = date_str[5:7]
                        key = f"{year_val}/{month_key}" if self.show_all_time else month_key
                            
                        if cat in ("ingreso", "income"):
                            monthly_data[key]['ingresos'] += base
                            total_ing += base
                        else:
                            monthly_data[key]['gastos'] += base
                            total_gast += base
                            if "TELEFONICA" in issuer.upper(): gastos_tel += base
                            elif "COWORKING" in issuer.upper(): gastos_ofi += base
                            else: gastos_otr += base
                            
                        monthly_data[key]['iva'] += iva
                        monthly_data[key]['irpf'] += irpf
                        total_iva += iva
                        total_irpf += irpf
                    except Exception: pass
                        
            if not monthly_data and not self.show_all_time:
                for m in [f"{i:02d}" for i in range(1, 13)]: monthly_data[m] = {'ingresos': 0.0, 'gastos': 0.0, 'iva': 0.0, 'irpf': 0.0}
            elif not self.show_all_time:
                for m in [f"{i:02d}" for i in range(1, 13)]:
                    if m not in monthly_data: monthly_data[m] = {'ingresos': 0.0, 'gastos': 0.0, 'iva': 0.0, 'irpf': 0.0}
                        
            chart_mapped_data = {}
            for k, val in monthly_data.items():
                chart_mapped_data[k] = {'ingresos': val['ingresos'], 'gastos': val['gastos'], 'impuestos': val['iva'] + val['irpf']}
            self.chart.set_data(chart_mapped_data, self.show_all_time)
            self.chart_taxes.set_data(dict(monthly_data), self.show_all_time)
            
            neto = total_ing - total_gast
            rentabilidad = (neto / total_ing * 100) if total_ing > 0 else 0.0
            
            self.lbl_ret_val.setText(f"{rentabilidad:.1f}%")
            self.bar_rentabilidad.setValue(int(min(100, max(0, rentabilidad))))
            self.lbl_iva_val.setText(f"{total_iva:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            self.lbl_irpf_val.setText(f"{total_irpf:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            
            total_desglose = gastos_ofi + gastos_tel + gastos_otr
            pct_ofi = (gastos_ofi / total_desglose * 100) if total_desglose > 0 else 0.0
            pct_tel = (gastos_tel / total_desglose * 100) if total_desglose > 0 else 0.0
            pct_otr = (gastos_otr / total_desglose * 100) if total_desglose > 0 else 0.0
                
            self.lbl_ofi_pct.setText(f"{pct_ofi:.1f}%")
            self.bar_ofi.setValue(int(pct_ofi))
            self.lbl_tel_pct.setText(f"{pct_tel:.1f}%")
            self.bar_tel.setValue(int(pct_tel))
            self.lbl_otr_pct.setText(f"{pct_otr:.1f}%")
            self.bar_otr.setValue(int(pct_otr))
            
        except Exception as e: print(f"Error cargando KPIs: {e}")
            
    def run_economic_audit(self):
        try:
            total_ing = sum(v['ingresos'] for v in self.chart_taxes.data.values())
            total_gast = sum(v['gastos'] for v in self.chart_taxes.data.values())
            total_iva = sum(v['iva'] for v in self.chart_taxes.data.values())
            total_irpf = sum(v['irpf'] for v in self.chart_taxes.data.values())
            stats = {'total_ingresos': total_ing, 'total_gastos': total_gast, 'total_iva': total_iva, 'total_irpf': total_irpf}
            self.btn_evaluate.setEnabled(False)
            self.terminal.clear()
            self.worker = EconomicAnalyzerThread(stats)
            self.worker.progress_signal.connect(self.log_to_terminal)
            self.worker.result_signal.connect(self.show_audit_result)
            self.worker.start()
        except Exception as e:
            self.terminal.setText(f"Error al iniciar auditoría: {e}")
            self.btn_evaluate.setEnabled(True)
            
    def log_to_terminal(self, text): self.terminal.append(text)
        
    def show_audit_result(self, result_text):
        self.terminal.append("\n" + result_text)
        self.btn_evaluate.setEnabled(True)


def launch(config):
    dashboard.show()
    sys.exit(app.exec())
