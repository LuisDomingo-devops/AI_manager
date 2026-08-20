import sys
import os
from pathlib import Path
os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false;qt.text.*=false"
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
                             QListWidget, QListWidgetItem, QTextEdit, QTextBrowser, QSplitter, QGroupBox, QDialog, QFormLayout, QMessageBox, QStackedWidget)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QEvent
from PyQt6.QtGui import QScreen, QPainter, QColor, QBrush, QPen, QPainterPath, QFont, QKeyEvent, QPixmap, QRadialGradient, QTextOption

from core.api_client import AlfonsoAPI
from core.processor import ResponseProcessor
from services.audio import AudioService
from core.alfonso_agent_logic import AlfonsoAgentLogic
from client.gui.widgets import DonutChartWidget, SparklineWidget
from client.gui.sidebar_widget import AlfonsoSidebarWidget, SIDEBAR_CATEGORIES
from client.gui.dialogs import (
    AlfonsoBaseDialog,
    AlfonsoComplianceDialog,
    AlfonsoSubscriptionDialog,
    CalendarWidget,
    AeatAutofillWidget,
    ConfigWidget,
    AlfonsoInvoiceConfirmDialog,
    MailWidget,
    AlfonsoOnboardingWizard,
    AlfonsoBankReconciliationDialog,
    AlfonsoBankConnectionsDialog,
    AlfonsoLedgerDialog,
    AlfonsoDocumentViewerDialog,
    AlfonsoArchiveBrowserDialog,
    AlfonsoKPIDashboardDialog,
    AlfonsoInitiateTransferDialog,
    AlfonsoManualEntryDialog,
    ProjectNavigatorDialog,
    AlertsWidget,
    AlfonsoCashFlowWidget,
    AlfonsoInvoiceEmitterWidget,
    AlfonsoPayrollWidget,
    AlfonsoVerifactuAuditWidget,
    AlfonsoBoeWidget,
    AlfonsoOfficialBooksWidget,
    AlfonsoBackupWidget,
    AlfonsoTenantAdvisorWidget
)



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
    confirm_invoice_requested = pyqtSignal(dict) # datos de la factura para popup



    def __init__(self, config):
        super().__init__()
        self.config = config
        
        # Cargar API Key persistente si existe en data/.api_key
        api_key = config.get('api_key', 'default_key')
        try:
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            key_file = os.path.join(parent_dir, "data", ".api_key")
            if os.path.exists(key_file):
                with open(key_file, "r", encoding="utf-8") as kf:
                    api_key = kf.read().strip()
        except Exception:
            pass
            
        self.api = AlfonsoAPI(config.get('url', 'http://localhost:8000'), api_key)
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

                        # Detectar confirmación humana requerida para facturación
                        pending_invoice = None
                        if response_data.get("type") == "multi_tool":
                            for r in response_data.get("results", []):
                                if r.get("tool") == "generate_invoice_pdf":
                                    res_tool = r.get("result", {})
                                    if res_tool.get("is_draft") and "requiere la confirmación" in res_tool.get("message", ""):
                                        pending_invoice = {**r.get("args", {}), **res_tool}
                        elif response_data.get("tool") == "generate_invoice_pdf":
                            res_tool = response_data.get("result", {})
                            if res_tool.get("is_draft") and "requiere la confirmación" in res_tool.get("message", ""):
                                pending_invoice = {**response_data.get("args", {}), **res_tool}

                        if pending_invoice:
                            self.confirm_invoice_requested.emit(pending_invoice)

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
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)
        
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
        self.setMinimumSize(40, 40)
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
        
        # 1. Scale photo to a standard size for processing
        img = raw_pixmap.toImage().scaled(240, 280, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        
        # Crop tightly to center face
        cx_img = (img.width() - 200) // 2
        cy_img = (img.height() - 240) // 2
        img = img.copy(cx_img, cy_img, 200, 240)
        img = img.convertToFormat(QImage.Format.Format_ARGB32)
        
        # 2. Apply soft vignette to black
        width, height = img.width(), img.height()
        mask_cx, mask_cy = width / 2.0, height / 2.0
        rx, ry = 85.0, 110.0
        
        for y in range(height):
            for x in range(width):
                col = QColor.fromRgb(img.pixel(x, y))
                dx = (x - mask_cx) / rx
                dy = (y - mask_cy) / ry
                dist = math.sqrt(dx*dx + dy*dy)
                
                if dist >= 1.0:
                    alpha_factor = 0.0
                else:
                    alpha_factor = math.cos(dist * math.pi / 2.0) ** 2
                
                r_final = int(col.red() * alpha_factor)
                g_final = int(col.green() * alpha_factor)
                b_final = int(col.blue() * alpha_factor)
                img.setPixel(x, y, QColor(r_final, g_final, b_final, col.alpha()).rgb())
        
        # 3. Generate CRT mask
        crt_mask = QImage(QSize(200, 240), QImage.Format.Format_ARGB32)
        crt_mask.fill(Qt.GlobalColor.transparent)
        
        m_painter = QPainter(crt_mask)
        m_painter.drawImage(0, 0, img)
        m_painter.setPen(QColor(0, 0, 0, 100))
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

        self._timer.start(30)
        self.update()

    def _draw_ethereal_core(self, painter, cx, cy, base_color):
        import math
        t = self._animation_phase
        scale = max(0.35, min(self.width(), self.height()) / 140.0)

        # Rotación 3D general del sistema orbital
        yaw = t * 0.4
        pitch = 0.65
        roll = t * 0.15

        r, g, b = base_color.red(), base_color.green(), base_color.blue()

        # 1. Aura de Resplandor Radial de Fondo
        glow_r = max(10, int(50 * scale))
        glow_grad = QRadialGradient(cx, cy, glow_r)
        glow_grad.setColorAt(0.0, QColor(r, g, b, 45))
        glow_grad.setColorAt(0.6, QColor(r, g, b, 12))
        glow_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(glow_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - glow_r), int(cy - glow_r), glow_r * 2, glow_r * 2)

        painter.save()

        def project_3d_point(x, y, z):
            cos_y, sin_y = math.cos(yaw), math.sin(yaw)
            x1 = x * cos_y + z * sin_y
            z1 = -x * sin_y + z * cos_y
            
            cos_p, sin_p = math.cos(pitch), math.sin(pitch)
            y2 = y * cos_p - z1 * sin_p
            z2 = y * sin_p + z1 * cos_p
            
            focal = 260.0
            dist = 220.0 + z2
            px = cx + (x1 * focal) / dist
            py = cy + (y2 * focal) / dist
            return px, py, z2

        # 2. Anillos Concentricos en 3D
        num_rings = 4
        base_radii = [14.0 * scale, 25.0 * scale, 37.0 * scale, 48.0 * scale]
        
        for idx, base_r in enumerate(base_radii):
            pulse = 0.0
            if self._state == "speaking":
                pulse = abs(math.sin(t * 9.0 - idx)) * (4.5 * scale)
            elif self._state == "listening":
                pulse = math.sin(t * 4.0 + idx) * (2.2 * scale)
            elif self._state == "thinking":
                pulse = math.sin(t * 8.0) * (1.2 * scale)
            else:
                pulse = math.sin(t * 1.5 + idx) * (1.0 * scale)
                
            ring_r = base_r + pulse
            
            ring_pts = []
            steps = 36
            for step in range(steps):
                angle = (2.0 * math.pi * step) / steps
                rx = ring_r * math.cos(angle)
                ry = ring_r * math.sin(angle)
                rz = math.sin(angle * 2.0) * (4.5 * scale)
                
                px, py, pz = project_3d_point(rx, ry, rz)
                ring_pts.append((px, py, pz))
            
            for i in range(steps):
                px1, py1, pz1 = ring_pts[i]
                px2, py2, pz2 = ring_pts[(i + 1) % steps]
                
                avg_z = (pz1 + pz2) / 2.0
                alpha = int(max(25, min(240, 140 + avg_z * 2.5)))
                
                pen = QPen(QColor(r, g, b, alpha), 1.0 if idx > 0 else 1.5)
                if idx == 1:
                    pen.setStyle(Qt.PenStyle.DashLine)
                elif idx == 2:
                    pen.setStyle(Qt.PenStyle.DotLine)
                    
                painter.setPen(pen)
                painter.drawLine(int(px1), int(py1), int(px2), int(py2))

        # 3. Nodos y Partículas Orbitantes
        num_particles = 12
        particle_pts = []
        for i in range(num_particles):
            angle = (2.0 * math.pi * i) / num_particles + (t * 0.2)
            p_r = (32.0 + math.sin(t * 0.8 + i) * 3.5) * scale
            
            px = p_r * math.cos(angle)
            py = p_r * math.sin(angle)
            pz = math.cos(angle * 3.0) * (8.0 * scale)
            
            px_p, py_p, pz_p = project_3d_point(px, py, pz)
            particle_pts.append((px_p, py_p, pz_p))

        for i in range(num_particles):
            px1, py1, pz1 = particle_pts[i]
            px2, py2, pz2 = particle_pts[(i + 1) % num_particles]
            avg_z = (pz1 + pz2) / 2.0
            alpha = int(max(10, min(100, 50 + avg_z * 1.5)))
            painter.setPen(QPen(QColor(r, g, b, alpha), 0.7))
            painter.drawLine(int(px1), int(py1), int(px2), int(py2))

        for px_p, py_p, pz_p in particle_pts:
            alpha = int(max(40, min(255, 180 + pz_p * 3.0)))
            size = max(2, int((2.8 + pz_p * 0.04) * scale))
            painter.setBrush(QBrush(QColor(r, g, b, alpha)))
            painter.setPen(QPen(QColor(255, 255, 255, int(alpha * 0.8)), 0.7))
            painter.drawEllipse(int(px_p - size/2), int(py_p - size/2), size, size)

        # 4. Núcleo Emisor Central
        core_size = max(5, int(7 * scale))
        if self._state == "speaking":
            core_size += int(abs(math.sin(t * 12.0)) * 3 * scale)
        
        core_grad = QRadialGradient(cx, cy, max(3, core_size))
        core_grad.setColorAt(0.0, QColor(255, 255, 255, 255))
        core_grad.setColorAt(0.4, QColor(r, g, b, 230))
        core_grad.setColorAt(1.0, QColor(r, g, b, 0))
        painter.setBrush(QBrush(core_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(int(cx - core_size), int(cy - core_size), core_size * 2, core_size * 2)

        # Ondas de sonido
        if self._state == "speaking":
            for wave_idx in range(3):
                wave_r = int((9 + ((t * 12 + wave_idx * 14) % 30)) * scale)
                wave_alpha = int(max(0, 150 - (wave_r * 2.8 / scale)))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor(r, g, b, wave_alpha), 1.1))
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
            jitter_x = random.randint(-2, 2)
            jitter_y = random.randint(-2, 2)

        # 1. Cuadrícula de Fondo CRT Estática
        painter.setPen(QPen(QColor(base_color.red(), base_color.green(), base_color.blue(), 12), 1))
        grid_size = 18
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


class AlfonsoWindowMaximizeButton(AlfonsoSystemButton):
    """Botón de maximizar / pantalla completa con cambios de estado."""
    def __init__(self, parent=None):
        super().__init__("□", parent)
        self.setObjectName("BtnMaximize")
        self.setFixedSize(20, 20)
        self.setStyleSheet("""
            QPushButton {
                background-color: #475569;
                border: none;
                color: #FFFFFF;
                font-weight: bold;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                padding: 0px;
                margin: 0px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #0284C7;
            }
            QPushButton:pressed {
                background-color: #0369A1;
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
        self.setWindowTitle("Alfonso Autónomo — Gestión Contable, Fiscal y Facturación Verifactu")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.resize(1440, 880)
        self.setMinimumSize(1200, 720)
        self._drag_pos = None 
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #080C14;
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

        self.attached_files = []
        self.current_typing_text = ""
        self.current_typing_index = 0
        self.text_mode_enabled = True
        self.chat_history = ""
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
        self.projects_dialog = None

        # Cargar API Key persistente
        api_key = config.get('api_key', 'default_key')
        try:
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            key_file = os.path.join(parent_dir, "data", ".api_key")
            if os.path.exists(key_file):
                with open(key_file, "r", encoding="utf-8") as kf:
                    api_key = kf.read().strip()
        except Exception:
            pass
            
        self.api_client = AlfonsoAPI(config.get('url', 'http://127.0.0.1:8000'), api_key)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.setup_layout()

        # Carpeta de logs local para la UI y el Agente (ui/logs)
        self.ui_logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(self.ui_logs_dir, exist_ok=True)

        # Carpeta de logs del servidor (WSL / app)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.logs_dir = os.path.join(base_dir, 'logs')
        if not os.path.isdir(self.logs_dir):
            import getpass
            current_user = getpass.getuser()
            wsl_logs = rf"\\wsl.localhost\Ubuntu\home\{current_user}\Alfonso\logs"
            if os.path.isdir(wsl_logs):
                self.logs_dir = wsl_logs
                
        self.current_log_file = "app.log"
        self.uptime_seconds = 67472
        
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
                from pathlib import Path
                home = Path.home()
                search_dirs = [filepath] if (filepath and os.path.isdir(filepath)) else [
                    str(home / "Desktop" / "Facturas_Para_Procesar"),
                    str(home / "Desktop" / "Facturas_Pendientes_Cobro"),
                    str(home / "Desktop" / "Facturas_Emitidas"),
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
            
            # Cargar API Key persistente
            api_key = self.config.get("api_key", "default_key")
            try:
                parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                key_file = os.path.join(parent_dir, "data", ".api_key")
                if os.path.exists(key_file):
                    with open(key_file, "r", encoding="utf-8") as kf:
                        api_key = kf.read().strip()
            except Exception:
                pass
                
            headers = {"X-API-Key": api_key}
            server_url = self.config.get("url", "http://127.0.0.1:8000")
            res = requests.get(f"{server_url}/tax/profile", headers=headers, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                if not data.get("configured", False):
                    api_client = AlfonsoAPI(self.config.get('url', 'http://127.0.0.1:8000'), api_key)
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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, '_drag_pos') and self._drag_pos is not None:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        super().mouseReleaseEvent(event)

    def setup_layout(self):
        root_layout = QVBoxLayout(self.central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ------------------ CABECERA GLOBAL SUPERIOR (44px, SIEMPRE VISIBLE) ------------------
        top_bar = QFrame()
        top_bar.setObjectName("GlobalTopBar")
        top_bar.setFixedHeight(44)
        top_bar.setStyleSheet("""
            #GlobalTopBar {
                background-color: #070B14;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(15, 0, 15, 0)
        top_bar_layout.setSpacing(12)

        # Logo & Título de Aplicación
        logo_icon = QLabel("▲")
        logo_icon.setStyleSheet("font-size: 16px; color: #00F0FF; font-weight: bold;")
        logo_title = QLabel("ALFONSO KONTA AI")
        logo_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF; letter-spacing: 1px;")
        
        sep = QLabel("│")
        sep.setStyleSheet("color: rgba(255, 255, 255, 0.15); font-size: 12px;")

        self.lbl_view_title = QLabel("● DASHBOARD FISCAL & EMPRESARIAL")
        self.lbl_view_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")

        top_bar_layout.addWidget(logo_icon)
        top_bar_layout.addWidget(logo_title)
        top_bar_layout.addWidget(sep)
        top_bar_layout.addWidget(self.lbl_view_title)
        top_bar_layout.addStretch()

        # Badge Verifactu SIF
        sif_badge = QLabel("🛡️ SIF VERI*FACTU RD 1007/2023 ● REGISTRO INALTERABLE")
        sif_badge.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 240, 255, 0.08);
                color: #00F0FF;
                border: 1px solid rgba(0, 240, 255, 0.25);
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 10px;
                font-weight: bold;
            }
        """)
        top_bar_layout.addWidget(sif_badge)

        # Fecha / Reloj
        self.clock_lbl = QPushButton("📅 Mayo 2024")
        self.clock_lbl.setStyleSheet("""
            QPushButton {
                background-color: #111827;
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 4px;
                color: #FFFFFF;
                padding: 4px 10px;
                font-size: 11px;
            }
        """)
        top_bar_layout.addWidget(self.clock_lbl)

        # Perfil Usuario
        user_pill = QLabel("👤 Luis Domingo (Autónomo)")
        user_pill.setStyleSheet("color: #E2E8F0; font-size: 11px; font-weight: 500; padding: 0 4px;")
        top_bar_layout.addWidget(user_pill)

        # Botones de Control de Ventana (SIEMPRE VISIBLES Y GLOBALES)
        self.btn_minimize = AlfonsoWindowMinimizeButton(self)
        self.btn_minimize.clicked.connect(self.showMinimized)
        top_bar_layout.addWidget(self.btn_minimize)

        self.btn_maximize = AlfonsoWindowMaximizeButton(self)
        self.btn_maximize.clicked.connect(self.toggle_maximize_restore)
        top_bar_layout.addWidget(self.btn_maximize)

        self.btn_shutdown = AlfonsoWindowCloseButton(self)
        self.btn_shutdown.clicked.connect(self.close_gui)
        top_bar_layout.addWidget(self.btn_shutdown)

        root_layout.addWidget(top_bar)

        # ------------------ CUERPO DE TRABAJO (3 COLUMNAS) ------------------
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ------------------ SIDEBAR IZQUIERDA CON CATEGORÍAS & SUBCATEGORÍAS ------------------
        self.sidebar = AlfonsoSidebarWidget(self)
        self.sidebar.category_selected.connect(self.on_sidebar_category_selected)
        self.sidebar.plan_clicked.connect(self.show_subscription_dialog)
        main_layout.addWidget(self.sidebar)

        # ------------------ CONTENIDO PRINCIPAL (DASHBOARD - INDEX 0) ------------------
        content_pane = QWidget()
        content_layout = QVBoxLayout(content_pane)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(14)

        # 1. Saludo y Estado del Negocio
        greeting_banner = QHBoxLayout()
        greeting_layout = QVBoxLayout()
        greeting_lbl = QLabel("Buenos días, Luis ☀️")
        greeting_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        sub_greeting = QLabel("Panel Ejecutivo Integral ● Contabilidad, Facturación Verifactu e Impuestos en Tiempo Real")
        sub_greeting.setStyleSheet("font-size: 11px; color: #94A3B8;")
        greeting_layout.addWidget(greeting_lbl)
        greeting_layout.addWidget(sub_greeting)
        greeting_banner.addLayout(greeting_layout)
        greeting_banner.addStretch()
        content_layout.addLayout(greeting_banner)

        # 2. Tarjetas KPI Horizontales
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        # Tarjeta 1: Ingresos
        card1 = QFrame()
        card1.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(14, 10, 14, 0)
        c1_title = QLabel("Ingresos  <span style='color: #10B981;'>▲ +18.6%</span>")
        c1_title.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_kpi_ingresos = QLabel("12.430,50 €")
        self.lbl_kpi_ingresos.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        c1_spark = SparklineWidget("#00F0FF", [10, 14, 12, 19, 15, 22, 25, 28, 32])
        c1_layout.addWidget(c1_title)
        c1_layout.addWidget(self.lbl_kpi_ingresos)
        c1_layout.addWidget(c1_spark)
        kpi_row.addWidget(card1)

        # Tarjeta 2: Gastos
        card2 = QFrame()
        card2.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        c2_layout = QVBoxLayout(card2)
        c2_layout.setContentsMargins(14, 10, 14, 0)
        c2_title = QLabel("Gastos  <span style='color: #F59E0B;'>▼ -7.3%</span>")
        c2_title.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_kpi_gastos = QLabel("6.256,90 €")
        self.lbl_kpi_gastos.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        c2_spark = SparklineWidget("#F59E0B", [22, 18, 19, 15, 17, 12, 14, 11, 8])
        c2_layout.addWidget(c2_title)
        c2_layout.addWidget(self.lbl_kpi_gastos)
        c2_layout.addWidget(c2_spark)
        kpi_row.addWidget(card2)

        # Tarjeta 3: Beneficio Neto
        card3 = QFrame()
        card3.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        c3_layout = QVBoxLayout(card3)
        c3_layout.setContentsMargins(14, 10, 14, 0)
        c3_title = QLabel("Beneficio Neto  <span style='color: #10B981;'>▲ +29.8%</span>")
        c3_title.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_kpi_beneficio = QLabel("6.173,60 €")
        self.lbl_kpi_beneficio.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        c3_spark = SparklineWidget("#10B981", [8, 12, 11, 16, 14, 19, 21, 23, 26])
        c3_layout.addWidget(c3_title)
        c3_layout.addWidget(self.lbl_kpi_beneficio)
        c3_layout.addWidget(c3_spark)
        kpi_row.addWidget(card3)

        # Tarjeta 4: IVA Soportado
        card4 = QFrame()
        card4.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        c4_layout = QVBoxLayout(card4)
        c4_layout.setContentsMargins(14, 10, 14, 0)
        c4_title = QLabel("IVA Soportado  <span style='color: #8B5CF6;'>23 facturas</span>")
        c4_title.setStyleSheet("font-size: 11px; color: #94A3B8;")
        self.lbl_kpi_iva = QLabel("1.356,78 €")
        self.lbl_kpi_iva.setStyleSheet("font-size: 18px; font-weight: bold; color: #FFFFFF;")
        c4_spark = SparklineWidget("#8B5CF6", [5, 8, 12, 6, 9, 14, 10, 11, 15], is_bar=True)
        c4_layout.addWidget(c4_title)
        c4_layout.addWidget(self.lbl_kpi_iva)
        c4_layout.addWidget(c4_spark)
        kpi_row.addWidget(card4)

        content_layout.addLayout(kpi_row)

        # 3. Filas Centrales: Gráfico Donut + Alertas + Movimientos Bancarios
        middle_grid = QHBoxLayout()
        middle_grid.setSpacing(12)

        # Columna 1: Facturas del Mes y Gráfico Donut
        donut_panel = QFrame()
        donut_panel.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        dp_layout = QVBoxLayout(donut_panel)
        dp_layout.setContentsMargins(14, 12, 14, 12)
        dp_title = QLabel("Facturas del Mes")
        dp_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        dp_layout.addWidget(dp_title)

        donut_inner = QHBoxLayout()
        self.donut_chart = DonutChartWidget()
        donut_inner.addWidget(self.donut_chart)

        legend_layout = QVBoxLayout()
        legend_layout.setSpacing(6)
        
        l1 = QLabel("● Pagadas (14) - 8.450 €")
        l1.setStyleSheet("color: #00F0FF; font-size: 11px;")
        l2 = QLabel("● Pendientes (3) - 2.150 €")
        l2.setStyleSheet("color: #F59E0B; font-size: 11px;")
        l3 = QLabel("● Vencidas (1) - 450 €")
        l3.setStyleSheet("color: #EF4444; font-size: 11px;")
        
        legend_layout.addWidget(l1)
        legend_layout.addWidget(l2)
        legend_layout.addWidget(l3)
        legend_layout.addStretch()
        donut_inner.addLayout(legend_layout)

        dp_layout.addLayout(donut_inner)
        middle_grid.addWidget(donut_panel, 2)

        # Columna 2: Alertas y Avisos AEAT
        alerts_panel = QFrame()
        alerts_panel.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        ap_layout = QVBoxLayout(alerts_panel)
        ap_layout.setContentsMargins(14, 12, 14, 12)
        ap_layout.setSpacing(8)

        ap_title = QLabel("Alertas y Próximos Vencimientos")
        ap_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        ap_layout.addWidget(ap_title)

        alert1 = QPushButton("⚠️ Modelo 303 (IVA 2T) vence en 12 días")
        alert1.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.1);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 6px;
                color: #F59E0B;
                text-align: left;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(245, 158, 11, 0.2); }
        """)
        alert1.clicked.connect(self.show_aeat)

        alert2 = QPushButton("ℹ️ 4 movimientos bancarios sin conciliar")
        alert2.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 240, 255, 0.08);
                border: 1px solid rgba(0, 240, 255, 0.2);
                border-radius: 6px;
                color: #00F0FF;
                text-align: left;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(0, 240, 255, 0.15); }
        """)
        alert2.clicked.connect(self.show_reconcile)

        alert3 = QPushButton("✅ SIF Veri*Factu: Cadena HASH válida y auditada")
        alert3.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.08);
                border: 1px solid rgba(16, 185, 129, 0.2);
                border-radius: 6px;
                color: #10B981;
                text-align: left;
                padding: 6px;
                font-size: 11px;
            }
            QPushButton:hover { background-color: rgba(16, 185, 129, 0.15); }
        """)
        alert3.clicked.connect(self.show_compliance)

        ap_layout.addWidget(alert1)
        ap_layout.addWidget(alert2)
        ap_layout.addWidget(alert3)
        ap_layout.addStretch()
        middle_grid.addWidget(alerts_panel, 2)

        content_layout.addLayout(middle_grid)

        # 4. Fila Inferior: Actividad Reciente + Accesos Rápidos
        footer_grid = QHBoxLayout()
        footer_grid.setSpacing(12)

        # Últimos Movimientos / Facturas
        recent_panel = QFrame()
        recent_panel.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        rp_layout = QVBoxLayout(recent_panel)
        rp_layout.setContentsMargins(14, 12, 14, 12)
        rp_title = QLabel("Últimos Movimientos del Negocio")
        rp_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        rp_layout.addWidget(rp_title)

        self.tbl_recent_invoices = QTableWidget(4, 4)
        self.tbl_recent_invoices.setHorizontalHeaderLabels(["Fecha", "Concepto / Cliente", "Tipo", "Importe"])
        self.tbl_recent_invoices.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tbl_recent_invoices.verticalHeader().setVisible(False)
        self.tbl_recent_invoices.setShowGrid(False)
        self.tbl_recent_invoices.setFixedHeight(120)
        self.tbl_recent_invoices.setStyleSheet("""
            QTableWidget {
                background: transparent;
                border: none;
                color: #F1F5F9;
                font-size: 11px;
            }
            QHeaderView::section {
                background-color: #0A0F1D;
                color: #64748B;
                border: none;
                font-size: 10px;
                font-weight: bold;
                padding: 4px;
            }
        """)

        mock_data = [
            ("14/05/2024", "Servicios Consultoría - InnoTech SL", "Factura Emitida", "+1.450,00 €"),
            ("12/05/2024", "Suscripción AWS Cloud Services", "Gasto Deducible", "-120,50 €"),
            ("10/05/2024", "Desarrollo Web - Marketing Digital", "Factura Emitida", "+850,00 €"),
            ("08/05/2024", "Cuota Autónomos RETA Mayo", "Seguridad Social", "-315,00 €")
        ]
        for row_idx, row in enumerate(mock_data):
            for col_idx, text in enumerate(row):
                item = QTableWidgetItem(text)
                if col_idx == 3:
                    if text.startswith("+"):
                        item.setForeground(QColor("#10B981"))
                    else:
                        item.setForeground(QColor("#EF4444"))
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl_recent_invoices.setItem(row_idx, col_idx, item)

        rp_layout.addWidget(self.tbl_recent_invoices)
        footer_grid.addWidget(recent_panel, 5)

        # Accesos Rápidos
        quick_panel = QFrame()
        quick_panel.setStyleSheet("background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 10px;")
        quick_layout = QVBoxLayout(quick_panel)
        quick_layout.setContentsMargins(14, 12, 14, 12)
        quick_title = QLabel("Accesos Rápidos")
        quick_title.setStyleSheet("font-size: 12px; font-weight: bold; color: #FFFFFF;")
        quick_layout.addWidget(quick_title)

        quick_buttons_layout = QHBoxLayout()
        quick_buttons_layout.setSpacing(8)

        q1 = QPushButton("⚡ Nueva Factura")
        q1.setCursor(Qt.CursorShape.PointingHandCursor)
        q1.clicked.connect(self.show_ledger)
        q1.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 240, 255, 0.1);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 6px;
                color: #00F0FF;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: rgba(0, 240, 255, 0.2); }
        """)
        quick_buttons_layout.addWidget(q1)

        q2 = QPushButton("🏦 Conciliar Bancos")
        q2.setCursor(Qt.CursorShape.PointingHandCursor)
        q2.clicked.connect(self.show_reconcile)
        q2.setStyleSheet("""
            QPushButton {
                background-color: rgba(16, 185, 129, 0.1);
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 6px;
                color: #10B981;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: rgba(16, 185, 129, 0.2); }
        """)
        quick_buttons_layout.addWidget(q2)

        q3 = QPushButton("📋 Modelo 303")
        q3.setCursor(Qt.CursorShape.PointingHandCursor)
        q3.clicked.connect(self.show_aeat)
        q3.setStyleSheet("""
            QPushButton {
                background-color: rgba(99, 102, 241, 0.1);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 6px;
                color: #6366F1;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: rgba(99, 102, 241, 0.2); }
        """)
        quick_buttons_layout.addWidget(q3)

        q4 = QPushButton("📁 Archivo Fiscal")
        q4.setCursor(Qt.CursorShape.PointingHandCursor)
        q4.clicked.connect(self.show_archive)
        q4.setStyleSheet("""
            QPushButton {
                background-color: rgba(245, 158, 11, 0.1);
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 6px;
                color: #F59E0B;
                font-weight: bold;
                font-size: 11px;
                padding: 8px;
            }
            QPushButton:hover { background-color: rgba(245, 158, 11, 0.2); }
        """)
        quick_buttons_layout.addWidget(q4)

        quick_layout.addLayout(quick_buttons_layout)
        footer_grid.addWidget(quick_panel, 4)

        content_layout.addLayout(footer_grid)

        # ------------------ CONTENIDO PRINCIPAL (QSTACKEDWIDGET) ------------------
        self.central_stack = QStackedWidget()

        # 0: Dashboard > Resumen Ejecutivo
        self.central_stack.addWidget(content_pane)

        # 1: Dashboard > Analítica & KPIs
        self.view_kpis = AlfonsoKPIDashboardDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_kpis)

        # 2: Dashboard > Previsión Cash Flow
        self.view_cashflow = AlfonsoCashFlowWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_cashflow)

        # 3: Facturación > Facturas Emitidas (7XX)
        self.view_invoices = AlfonsoLedgerDialog(self, self.api_client, embedded=True)
        self.central_stack.addWidget(self.view_invoices)

        # 4: Facturación > Nueva Factura / FacturaE B2B
        self.view_invoice_emitter = AlfonsoInvoiceEmitterWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_invoice_emitter)

        # 5: Facturación > Veri*Factu & Huella Hash
        self.view_verifactu_audit = AlfonsoVerifactuAuditWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_verifactu_audit)

        # 6: Gastos > Libro de Gastos (6XX)
        self.view_expenses = AlfonsoLedgerDialog(self, self.api_client, embedded=True)
        self.central_stack.addWidget(self.view_expenses)

        # 7: Gastos > Captura & Extracción OCR
        self.view_ocr = AlfonsoDocumentViewerDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_ocr)

        # 8: Gastos > Registro Manual de Gasto
        self.view_manual_entry = AlfonsoManualEntryDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_manual_entry)

        # 9: Bancos > Conciliación Bancaria PSD2
        self.view_banks = AlfonsoBankReconciliationDialog(self, self.api_client, embedded=True)
        self.central_stack.addWidget(self.view_banks)

        # 10: Bancos > Cuentas Conectadas Open Banking
        self.view_bank_connections = AlfonsoBankConnectionsDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_bank_connections)

        # 11: Bancos > Emisión de Transferencias SEPA
        self.view_transfers = AlfonsoInitiateTransferDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_transfers)

        # 12: Impuestos > Modelos Trimestrales (303, 130)
        self.view_taxes = AeatAutofillWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_taxes)

        # 13: Impuestos > Sede Electrónica & Playwright
        self.view_aeat_auto = AeatAutofillWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_aeat_auto)

        # 14: Impuestos > Calendario Fiscal & Vencimientos
        self.view_calendar = CalendarWidget(self.api_client, self, embedded=True)
        self.central_stack.addWidget(self.view_calendar)

        # 15: Impuestos > Monitor BOE & Leyes
        self.view_boe = AlfonsoBoeWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_boe)

        # 16: Laboral > Empleados & Contratos
        self.view_employees = AlfonsoPayrollWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_employees)

        # 17: Laboral > Generador de Nóminas PDF
        self.view_payrolls = AlfonsoPayrollWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_payrolls)

        # 18: Laboral > Seguridad Social & TGSS
        self.view_tgss = AlfonsoPayrollWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_tgss)

        # 19: Documentos > Archivo Fiscal Digital
        self.view_docs = AlfonsoArchiveBrowserDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_docs)

        # 20: Documentos > Visor Documental con IA
        self.view_doc_viewer = AlfonsoDocumentViewerDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_doc_viewer)

        # 21: Documentos > Libros Oficiales AEAT (Excel/CSV)
        self.view_official_books = AlfonsoOfficialBooksWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_official_books)

        # 22: Asistente > Chat IA & Voz Alfonso
        self.view_ai_chat = AlfonsoComplianceDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_ai_chat)

        # 23: Asistente > Alfonso Mail Inteligente
        self.view_mail = MailWidget(self.api_client, self, embedded=True)
        self.central_stack.addWidget(self.view_mail)

        # 24: Asistente > Agenda & Citas Previas
        self.view_agenda = CalendarWidget(self.api_client, self, embedded=True)
        self.central_stack.addWidget(self.view_agenda)

        # 25: Asistente > Navegador de Proyectos
        self.view_projects = ProjectNavigatorDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_projects)

        # 26: Cumplimiento > Declaración Responsable SIF (RD 1007/2023)
        self.view_advisor = AlfonsoComplianceDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_advisor)

        # 27: Cumplimiento > Auditoría de Inmutabilidad
        self.view_audit_ledger = AlfonsoVerifactuAuditWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_audit_ledger)

        # 28: Cumplimiento > Panel Asesor / Gestoría
        self.view_tenant_advisor = AlfonsoTenantAdvisorWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_tenant_advisor)

        # 29: Sistema > Perfil Fiscal del Autónomo
        self.view_config = ConfigWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_config)

        # 30: Sistema > IA, Voz & Dispositivos
        self.view_voice_config = ConfigWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_voice_config)

        # 31: Sistema > Copias de Seguridad & Restauración
        self.view_backups = AlfonsoBackupWidget(self, embedded=True)
        self.central_stack.addWidget(self.view_backups)

        # 32: Sistema > Suscripción & Licencia
        self.view_subscription = AlfonsoSubscriptionDialog(self, embedded=True)
        self.central_stack.addWidget(self.view_subscription)

        main_layout.addWidget(self.central_stack, 1)

        # ------------------ PANEL DERECHO: CHAT ASISTENTE IA (380px) ------------------
        chat_panel = QFrame()
        chat_panel.setObjectName("ChatPanel")
        chat_panel.setFixedWidth(380)
        chat_panel.setStyleSheet("""
            #ChatPanel {
                background-color: #0A0F1D;
                border-left: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)
        chat_layout = QVBoxLayout(chat_panel)
        chat_layout.setContentsMargins(12, 16, 12, 14)
        chat_layout.setSpacing(8)

        # 1. Cabecera del Chat con Estado
        chat_header = QHBoxLayout()
        chat_badge = QLabel("● ALFONSO AI ASISTENTE")
        chat_badge.setStyleSheet("color: #00F0FF; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
        
        self.state_lbl = QLabel("STANDBY")
        self.state_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #00F0FF; letter-spacing: 1px;")
        
        chat_header.addWidget(chat_badge)
        chat_header.addStretch()
        chat_header.addWidget(self.state_lbl)
        chat_layout.addLayout(chat_header)

        # Indicador de Sesión Activa
        self.lbl_active_session = QLabel("SESIÓN ACTIVA: DEFAULT")
        self.lbl_active_session.setStyleSheet("""
            font-family: 'Consolas', monospace;
            font-size: 9px;
            color: #00FF66;
            background-color: rgba(0, 255, 102, 0.05);
            border: 1px solid rgba(0, 255, 102, 0.15);
            border-radius: 4px;
            padding: 2px 6px;
        """)
        chat_layout.addWidget(self.lbl_active_session)

        # 2. Cubículo Holográfico de Rostro / Voz
        hologram_cubicle = QFrame()
        hologram_cubicle.setObjectName("HologramCubicle")
        hologram_cubicle.setFixedHeight(125)
        hologram_cubicle.setStyleSheet("""
            #HologramCubicle {
                background-color: #070B14;
                border: 1px solid rgba(0, 240, 255, 0.2);
                border-radius: 10px;
            }
        """)
        hologram_layout = QVBoxLayout(hologram_cubicle)
        hologram_layout.setContentsMargins(4, 4, 4, 4)
        self.animated_wave = AnimatedWaveWidget(self)
        hologram_layout.addWidget(self.animated_wave)
        chat_layout.addWidget(hologram_cubicle)

        # 3. Medidor VU de micrófono
        vu_layout = QHBoxLayout()
        self.mic_name_lbl = QLabel("MIC: ACTIVO")
        self.mic_name_lbl.setStyleSheet("font-size: 9px; color: #64748B; font-family: monospace;")
        self.vu_meter = QProgressBar()
        self.vu_meter.setFixedHeight(4)
        self.vu_meter.setTextVisible(False)
        self.vu_meter.setStyleSheet("""
            QProgressBar { background: rgba(255,255,255,0.05); border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #00F0FF; border-radius: 2px; }
        """)
        vu_layout.addWidget(self.mic_name_lbl)
        vu_layout.addWidget(self.vu_meter)
        chat_layout.addLayout(vu_layout)

        # 4. Historial de Mensajes con Markdown
        self.chat_lbl = QTextBrowser()
        self.chat_lbl.setOpenExternalLinks(True)
        self.chat_lbl.setStyleSheet("""
            QTextBrowser {
                background-color: #111827;
                border: 1px solid rgba(255, 255, 255, 0.05);
                border-radius: 8px;
                color: #F8FAFC;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                padding: 8px;
            }
        """)
        self.chat_history = "### 🤖 ¡Hola! Soy Alfonso, tu asistente contable.\n\nPuedes pedirme por voz o texto que emita facturas, concilie bancos, revise impuestos o calcule tus modelos de la AEAT.\n\n*Arrastra facturas o tickets aquí para procesarlos automáticamente.*"
        self.chat_lbl.setMarkdown(self.chat_history)
        chat_layout.addWidget(self.chat_lbl, 1)

        # 5. Contenedor de Archivos Adjuntos / Arrastrados
        self.attachments_container = QWidget()
        self.attachments_container.setVisible(False)
        self.attachments_layout = QGridLayout(self.attachments_container)
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)
        self.attachments_layout.setSpacing(4)
        chat_layout.addWidget(self.attachments_container)

        # 6. Caja de Entrada de Texto
        self.text_input = ChatTextInput()
        self.text_input.setFixedHeight(55)
        self.text_input.setPlaceholderText("Escribe a Alfonso o arrastra facturas aquí... (Shift+Enter para salto)")
        self.text_input.file_dropped.connect(self.handle_file_drop)
        self.text_input.setStyleSheet("""
            QTextEdit {
                background-color: #111827;
                border: 1px solid rgba(0, 240, 255, 0.2);
                border-radius: 6px;
                color: #FFFFFF;
                padding: 6px;
                font-size: 11px;
            }
            QTextEdit:focus {
                border: 1px solid #00F0FF;
            }
        """)
        chat_layout.addWidget(self.text_input)

        # 7. Botonera de Control del Chat
        chat_btn_layout = QHBoxLayout()
        chat_btn_layout.setSpacing(6)

        self.btn_mode = QPushButton("VOZ / TECLADO")
        self.btn_mode.setFixedHeight(28)
        self.btn_mode.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 240, 255, 0.1);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 6px;
                color: #00F0FF;
                font-size: 10px;
                font-weight: bold;
                padding: 0 8px;
            }
            QPushButton:hover { background-color: rgba(0, 240, 255, 0.2); }
        """)
        self.btn_mode.clicked.connect(self.toggle_text_mode)

        self.btn_clear = QPushButton("Limpiar")
        self.btn_clear.setFixedHeight(28)
        self.btn_clear.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 6px;
                color: #94A3B8;
                font-size: 10px;
                padding: 0 8px;
            }
            QPushButton:hover { color: #FFFFFF; background: rgba(255,255,255,0.05); }
        """)
        self.btn_clear.clicked.connect(self.clear_chat)

        btn_send = QPushButton("Enviar ↵")
        btn_send.setFixedHeight(28)
        btn_send.setStyleSheet("""
            QPushButton {
                background-color: #00F0FF;
                border: none;
                border-radius: 6px;
                color: #0A0F1D;
                font-size: 10px;
                font-weight: bold;
                padding: 0 12px;
            }
            QPushButton:hover { background-color: #38BDF8; }
        """)
        btn_send.clicked.connect(self.send_text_message)

        chat_btn_layout.addWidget(self.btn_mode)
        chat_btn_layout.addWidget(self.btn_clear)
        chat_btn_layout.addStretch()
        chat_btn_layout.addWidget(btn_send)
        chat_layout.addLayout(chat_btn_layout)

        main_layout.addWidget(chat_panel)
        root_layout.addLayout(main_layout, 1)

    def show_subscription_dialog(self):
        try:
            from client.gui.dialogs.base import AlfonsoSubscriptionDialog
            dialog = AlfonsoSubscriptionDialog(self)
            dialog.exec()
        except Exception as e:
            print(f"Error abriendo diálogo de suscripción: {e}")
        pass

    def setup_body_columns(self):
        pass


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
        from pathlib import Path
        dest_dir = str(Path.home() / "Desktop" / "Facturas_Para_Procesar")
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
        self.thread.confirm_invoice_requested.connect(self.show_invoice_confirmation)
        self.thread.start()

    def on_sidebar_category_selected(self, cat_id: str, subcat_id: str, title: str):
        """Manejador ejecutado al pulsar cualquier subcategoría en el panel lateral."""
        self.switch_to_view((cat_id, subcat_id))

    def switch_to_view(self, target):
        """Cambia dinámicamente la vista del panel central (QStackedWidget) y actualiza el título y menú."""
        mapping = {
            # Panel de Control
            ("dashboard", "resumen_ejecutivo"): (0, "PANEL DE CONTROL > RESUMEN EJECUTIVO", "dashboard", "resumen_ejecutivo"),
            ("dashboard", "kpis_analitica"): (1, "PANEL DE CONTROL > ANALÍTICA & KPIS", "dashboard", "kpis_analitica"),
            ("dashboard", "prevision_cashflow"): (2, "PANEL DE CONTROL > PREVISIÓN DE TESORERÍA", "dashboard", "prevision_cashflow"),

            # Facturación & Ventas
            ("facturacion", "facturas_emitidas"): (3, "FACTURACIÓN & VENTAS > FACTURAS EMITIDAS (7XX)", "facturacion", "facturas_emitidas"),
            ("facturacion", "nueva_factura_b2b"): (4, "FACTURACIÓN & VENTAS > NUEVA FACTURA / FACTURAE B2B", "facturacion", "nueva_factura_b2b"),
            ("facturacion", "verifactu_sif"): (5, "FACTURACIÓN & VENTAS > VERI*FACTU & HUELLA HASH", "facturacion", "verifactu_sif"),

            # Gastos & Compras
            ("gastos", "libro_gastos"): (6, "GASTOS & COMPRAS > LIBRO DE GASTOS Y COMPRAS (6XX)", "gastos", "libro_gastos"),
            ("gastos", "ocr_extraccion"): (7, "GASTOS & COMPRAS > CAPTURA & EXTRACCIÓN OCR", "gastos", "ocr_extraccion"),
            ("gastos", "registro_manual"): (8, "GASTOS & COMPRAS > REGISTRO MANUAL DE GASTO", "gastos", "registro_manual"),

            # Banca & Tesorería
            ("bancos", "conciliacion_bancaria"): (9, "BANCA & TESORERÍA > CONCILIACIÓN INTELIGENTE PSD2", "bancos", "conciliacion_bancaria"),
            ("bancos", "conexiones_psd2"): (10, "BANCA & TESORERÍA > CUENTAS BANCARIAS VINCULADAS", "bancos", "conexiones_psd2"),
            ("bancos", "transferencias_pagos"): (11, "BANCA & TESORERÍA > EMISIÓN DE TRANSFERENCIAS SEPA", "bancos", "transferencias_pagos"),

            # Fiscalidad & AEAT
            ("impuestos", "modelos_trimestrales"): (12, "FISCALIDAD & AEAT > MODELOS TRIMESTRALES (303, 130)", "impuestos", "modelos_trimestrales"),
            ("impuestos", "automatizacion_aeat"): (13, "FISCALIDAD & AEAT > SEDE ELECTRÓNICA & PLAYWRIGHT", "impuestos", "automatizacion_aeat"),
            ("impuestos", "calendario_fiscal"): (14, "FISCALIDAD & AEAT > CALENDARIO FISCAL & VENCIMIENTOS", "impuestos", "calendario_fiscal"),
            ("impuestos", "novedades_boe"): (15, "FISCALIDAD & AEAT > MONITOR BOE & NOVEDADES FISCALES", "impuestos", "novedades_boe"),

            # Laboral & Nóminas
            ("laboral", "empleados_contratos"): (16, "LABORAL & NÓMINAS > GESTIÓN DE EMPLEADOS Y CONTRATOS", "laboral", "empleados_contratos"),
            ("laboral", "generador_nominas"): (17, "LABORAL & NÓMINAS > GENERADOR OFICIAL DE NÓMINAS PDF", "laboral", "generador_nominas"),
            ("laboral", "afiliacion_tgss"): (18, "LABORAL & NÓMINAS > SEGURIDAD SOCIAL & TGSS / RETA", "laboral", "afiliacion_tgss"),

            # Documentos & Archivo
            ("documentos", "archivo_fiscal"): (19, "DOCUMENTOS & ARCHIVO > ARCHIVO FISCAL DIGITAL", "documentos", "archivo_fiscal"),
            ("documentos", "visor_documental"): (20, "DOCUMENTOS & ARCHIVO > VISOR DOCUMENTAL CON IA", "documentos", "visor_documental"),
            ("documentos", "libros_oficiales_aeat"): (21, "DOCUMENTOS & ARCHIVO > LIBROS OFICIALES AEAT", "documentos", "libros_oficiales_aeat"),

            # Asistente & Comunicación
            ("comunicacion", "asistente_ia"): (22, "ASISTENTE & COMUNICACIÓN > CHAT IA & VOZ ALFONSO", "comunicacion", "asistente_ia"),
            ("comunicacion", "correo_inteligente"): (23, "ASISTENTE & COMUNICACIÓN > ALFONSO MAIL INTELIGENTE", "comunicacion", "correo_inteligente"),
            ("comunicacion", "agenda_citas"): (24, "ASISTENTE & COMUNICACIÓN > AGENDA & CITAS PREVIAS", "comunicacion", "agenda_citas"),
            ("comunicacion", "proyectos_sesiones"): (25, "ASISTENTE & COMUNICACIÓN > NAVEGADOR DE PROYECTOS", "comunicacion", "proyectos_sesiones"),

            # Auditoría & Asesoría
            ("cumplimiento", "declaracion_sif"): (26, "AUDITORÍA & ASESORÍA > DECLARACIÓN RESPONSABLE SIF", "cumplimiento", "declaracion_sif"),
            ("cumplimiento", "auditoria_inmutabilidad"): (27, "AUDITORÍA & ASESORÍA > AUDITORÍA DE INMUTABILIDAD", "cumplimiento", "auditoria_inmutabilidad"),
            ("cumplimiento", "panel_asesor"): (28, "AUDITORÍA & ASESORÍA > PANEL GESTORÍA & MULTI-INQUILINO", "cumplimiento", "panel_asesor"),

            # Sistema & Configuración
            ("sistema", "perfil_fiscal"): (29, "SISTEMA & CONFIGURACIÓN > PERFIL FISCAL DEL AUTÓNOMO", "sistema", "perfil_fiscal"),
            ("sistema", "voz_modelos_ia"): (30, "SISTEMA & CONFIGURACIÓN > IA, VOZ & DISPOSITIVOS", "sistema", "voz_modelos_ia"),
            ("sistema", "copias_seguridad"): (31, "SISTEMA & CONFIGURACIÓN > COPIAS DE SEGURIDAD & RESTAURACIÓN", "sistema", "copias_seguridad"),
            ("sistema", "suscripcion_licencia"): (32, "SISTEMA & CONFIGURACIÓN > SUSCRIPCIÓN & LICENCIA", "sistema", "suscripcion_licencia"),

            # Legacy string aliases
            "Dashboard": (0, "PANEL DE CONTROL > RESUMEN EJECUTIVO", "dashboard", "resumen_ejecutivo"),
            "Facturas": (3, "FACTURACIÓN & VENTAS > FACTURAS EMITIDAS (7XX)", "facturacion", "facturas_emitidas"),
            "Gastos": (6, "GASTOS & COMPRAS > LIBRO DE GASTOS Y COMPRAS (6XX)", "gastos", "libro_gastos"),
            "Bancos": (9, "BANCA & TESORERÍA > CONCILIACIÓN INTELIGENTE PSD2", "bancos", "conciliacion_bancaria"),
            "Impuestos": (12, "FISCALIDAD & AEAT > MODELOS TRIMESTRALES (303, 130)", "impuestos", "modelos_trimestrales"),
            "Documentos": (19, "DOCUMENTOS & ARCHIVO > ARCHIVO FISCAL DIGITAL", "documentos", "archivo_fiscal"),
            "Correo": (23, "ASISTENTE & COMUNICACIÓN > ALFONSO MAIL INTELIGENTE", "comunicacion", "correo_inteligente"),
            "Calendario": (14, "FISCALIDAD & AEAT > CALENDARIO FISCAL & VENCIMIENTOS", "impuestos", "calendario_fiscal"),
            "Asesor": (26, "AUDITORÍA & ASESORÍA > DECLARACIÓN RESPONSABLE SIF", "cumplimiento", "declaracion_sif"),
            "Configuración": (29, "SISTEMA & CONFIGURACIÓN > PERFIL FISCAL DEL AUTÓNOMO", "sistema", "perfil_fiscal")
        }

        if isinstance(target, tuple):
            info = mapping.get(target, (0, "PANEL DE CONTROL > RESUMEN EJECUTIVO", "dashboard", "resumen_ejecutivo"))
            idx, title_text, cat_id, subcat_id = info
        elif isinstance(target, str):
            info = mapping.get(target, (0, f"● {target.upper()}", "dashboard", "resumen_ejecutivo"))
            idx, title_text, cat_id, subcat_id = info
        elif isinstance(target, int):
            idx = target
            cat_id = "dashboard"
            subcat_id = "resumen_ejecutivo"
            title_text = "PANEL DE CONTROL"
            for k, val in mapping.items():
                if isinstance(k, tuple) and val[0] == idx:
                    idx, title_text, cat_id, subcat_id = val
                    break
        else:
            idx = 0
            cat_id = "dashboard"
            subcat_id = "resumen_ejecutivo"
            title_text = "PANEL DE CONTROL > RESUMEN EJECUTIVO"

        if hasattr(self, 'central_stack'):
            self.central_stack.setCurrentIndex(idx)

        if hasattr(self, 'lbl_view_title'):
            self.lbl_view_title.setText(f"● {title_text}")

        # Sincronizar selección en la barra lateral
        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'set_active'):
            self.sidebar.set_active(cat_id, subcat_id)

        # Actualizar datos de la vista activa
        try:
            if idx == 0:
                self.update_business_metrics()
            elif idx == 1 and hasattr(self, 'view_kpis') and hasattr(self.view_kpis, 'load_kpi_data'):
                self.view_kpis.load_kpi_data()
            elif idx == 2 and hasattr(self, 'view_cashflow') and hasattr(self.view_cashflow, 'load_cash_flow_data'):
                self.view_cashflow.load_cash_flow_data()
            elif idx == 3 and hasattr(self, 'view_invoices'):
                if hasattr(self.view_invoices, 'set_filter'):
                    self.view_invoices.set_filter("ingreso")
                elif hasattr(self.view_invoices, 'load_ledger_data'):
                    self.view_invoices.load_ledger_data()
            elif idx == 5 and hasattr(self, 'view_verifactu_audit') and hasattr(self.view_verifactu_audit, 'load_audit_data'):
                self.view_verifactu_audit.load_audit_data()
            elif idx == 6 and hasattr(self, 'view_expenses'):
                if hasattr(self.view_expenses, 'set_filter'):
                    self.view_expenses.set_filter("gasto")
                elif hasattr(self.view_expenses, 'load_ledger_data'):
                    self.view_expenses.load_ledger_data()
            elif idx == 9 and hasattr(self, 'view_banks') and hasattr(self.view_banks, 'load_movements'):
                self.view_banks.load_movements()
            elif idx in (12, 13) and hasattr(self, 'view_taxes') and hasattr(self.view_taxes, 'calculate_taxes_live'):
                self.view_taxes.calculate_taxes_live()
            elif idx == 14 and hasattr(self, 'view_calendar') and hasattr(self.view_calendar, 'load_events'):
                self.view_calendar.load_events()
            elif idx in (16, 17, 18) and hasattr(self, 'view_employees') and hasattr(self.view_employees, 'load_employees'):
                self.view_employees.load_employees()
            elif idx == 19 and hasattr(self, 'view_docs') and hasattr(self.view_docs, 'refresh_file_list'):
                self.view_docs.refresh_file_list()
            elif idx == 23 and hasattr(self, 'view_mail') and hasattr(self.view_mail, 'load_emails'):
                self.view_mail.load_emails()
        except Exception as e:
            print(f"Error actualizando vista {title_text}: {e}")

    def show_dashboard(self):
        self.switch_to_view("Dashboard")

    def show_ledger(self):
        self.switch_to_view("Facturas")

    def show_expenses(self):
        self.switch_to_view("Gastos")

    def show_reconcile(self):
        self.switch_to_view("Bancos")

    def show_aeat(self):
        self.switch_to_view("Impuestos")

    def show_archive(self):
        self.switch_to_view("Documentos")

    def show_mail(self):
        self.switch_to_view("Correo")

    def show_calendar(self):
        self.switch_to_view("Calendario")

    def show_compliance(self):
        self.switch_to_view("Asesor")

    def show_config(self):
        self.switch_to_view("Configuración")

    def show_subscription_dialog(self):
        self.switch_to_view("Configuración")

    def hide_calendar(self):
        self.switch_to_view("Dashboard")

    def hide_mail(self):
        self.switch_to_view("Dashboard")

    def hide_config(self):
        self.switch_to_view("Dashboard")

    def reload_calendar_events(self):
        if hasattr(self, 'view_calendar') and hasattr(self.view_calendar, 'load_events'):
            self.view_calendar.load_events()

    def reload_mail_events(self):
        if hasattr(self, 'view_mail') and hasattr(self.view_mail, 'load_emails'):
            self.view_mail.load_emails()

    def show_invoice_confirmation(self, invoice_data):
        try:
            dialog = AlfonsoInvoiceConfirmDialog(self, invoice_data)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.confirmed:
                invoice_id = invoice_data.get("invoice_id")
                self.thread.send_text_message(f"Confirmo la emisión y registro de la factura {invoice_id} en la AEAT de forma firme.")
        except Exception as e:
            print(f"Error mostrando confirmación de factura: {e}")

    def update_module_button_states(self):
        pass

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
        if hasattr(self, 'animated_wave') and self.animated_wave:
            self.animated_wave.set_state(state)
        if hasattr(self, 'state_lbl') and self.state_lbl:
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
        if hasattr(self, 'clock_lbl') and self.clock_lbl:
            self.clock_lbl.setText(f"📅 {date_str} - {time_str}")
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
            
            # Contadores de facturas reales para el donut chart
            total_facturas = 0
            pagadas = 0
            pendientes = 0
            rechazadas = 0
            iva_soportado = 0.0

            with _get_connection() as conn:
                cursor = conn.cursor()
                
                # 1. Calcular Saldo Bancario
                cursor.execute("SELECT SUM(amount) FROM bank_movements")
                row_bank = cursor.fetchone()
                if row_bank and row_bank[0] is not None:
                    saldo = float(row_bank[0])
                    
                # 2. Calcular Ingresos, Gastos e IVA Soportado
                cursor.execute("SELECT base_imponible, category, quarter, status, iva_amount FROM invoices WHERE year = 2026")
                invs = cursor.fetchall()
                for inv in invs:
                    try:
                        base = float(encryptor.decrypt(inv["base_imponible"]))
                        total_facturas += 1
                        
                        # Conteo por estado de pago
                        inv_status = inv.get("status")
                        if inv_status in ("pagada", "paid"):
                            pagadas += 1
                        elif inv_status in ("rechazada", "rejected"):
                            rechazadas += 1
                        else:
                            pendientes += 1
                            
                        # Clasificación ingreso vs gasto
                        if inv["category"] in ("ingreso", "income"):
                            ingresos += base
                        elif inv["category"] in ("gasto", "expense"):
                            gastos += base
                            if inv.get("iva_amount"):
                                try:
                                    iva_soportado += float(encryptor.decrypt(inv["iva_amount"]))
                                except Exception:
                                    pass
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
                        
            # Actualizar textos de la interfaz en tiempo real
            if hasattr(self, 'lbl_saldo_banco_main') and self.lbl_saldo_banco_main:
                self.lbl_saldo_banco_main.setText(f"{saldo:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
                if saldo >= 0:
                    self.lbl_saldo_banco_main.setStyleSheet("font-size: 18px; font-weight: bold; color: #10B981;")
                else:
                    self.lbl_saldo_banco_main.setStyleSheet("font-size: 18px; font-weight: bold; color: #EF4444;")
            
            # Tarjetas de KPIs superiores
            if hasattr(self, 'lbl_kpi_ingresos') and self.lbl_kpi_ingresos:
                self.lbl_kpi_ingresos.setText(f"{ingresos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            if hasattr(self, 'lbl_kpi_gastos') and self.lbl_kpi_gastos:
                self.lbl_kpi_gastos.setText(f"{gastos:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            if hasattr(self, 'lbl_kpi_beneficio') and self.lbl_kpi_beneficio:
                self.lbl_kpi_beneficio.setText(f"{(ingresos - gastos):,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            if hasattr(self, 'lbl_kpi_iva') and self.lbl_kpi_iva:
                self.lbl_kpi_iva.setText(f"{iva_soportado:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."))
            
            # Actualizar el gráfico circular donut dinámicamente con los estados reales
            if total_facturas > 0:
                if hasattr(self, 'donut_widget') and self.donut_widget:
                    self.donut_widget.set_values(total_facturas, pagadas, pendientes, rechazadas)
                if hasattr(self, 'leg1') and self.leg1: self.leg1.setText(f"● Pagadas ({pagadas})")
                if hasattr(self, 'leg2') and self.leg2: self.leg2.setText(f"● Pendientes ({pendientes})")
                if hasattr(self, 'leg3') and self.leg3: self.leg3.setText(f"● Rechazadas ({rechazadas})")
            
            # Actualizar el gráfico de barras del trimestre (si existe)
            if hasattr(self, 'bar_chart') and self.bar_chart:
                self.bar_chart.update_data(ingresos_trim, gastos_trim)

        except Exception as e:
            print(f"Error updating business telemetry: {e}")

    def toggle_maximize_restore(self):
        """Alterna entre pantalla completa (maximizado) y tamaño de ventana normal."""
        if self.isMaximized():
            self.showNormal()
            if hasattr(self, 'btn_maximize'):
                self.btn_maximize.setText("□")
        else:
            self.showMaximized()
            if hasattr(self, 'btn_maximize'):
                self.btn_maximize.setText("❐")

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



from client.gui.dialogs import *

def launch(config):
    app = QApplication(sys.argv)
    dashboard = AlfonsoHUDDashboard(config)
    dashboard.show()
    dashboard.raise_()
    dashboard.activateWindow()
    sys.exit(app.exec())
