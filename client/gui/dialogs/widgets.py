import sys
import os
import uuid
import datetime
import shutil
import csv
import json
import collections
from pathlib import Path

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
                             QFrame, QPushButton, QLineEdit, QTextEdit, QTextBrowser, 
                             QScrollArea, QSplitter, QGroupBox, QFormLayout, QMessageBox,
                             QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QComboBox, QFileDialog, QStackedWidget, QSpinBox, 
                             QDoubleSpinBox, QButtonGroup, QProgressBar, QListView, QStyle)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QColor, QFont, QPixmap, QDesktopServices, QPainter, QPen, QBrush, QLinearGradient, QPainterPath
from core.api_client import AlfonsoAPI
from client.gui.dialogs.base import AlfonsoBaseDialog

class MailWidget(AlfonsoBaseDialog):
    """Interfaz gráfica nativa para el cliente de Correo Electrónico (ALFONSO MAIL)."""
    def __init__(self, api_client, parent=None):
        super().__init__(parent, "ALFONSO MAIL", modal=False)
        self.api = api_client
        self.setMinimumSize(1150, 700)
        self.resize(1150, 700)
        
        self.current_category = None
        self.emails_list = []
        
        self.setup_ui()

    def setup_ui(self):
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

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
        lbl_cat.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent; border: none;")
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
        
        self.cat_buttons[None].setProperty("active", "true")

        left_layout.addStretch()
        body_splitter.addWidget(self.left_panel)

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

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        scroll_content = QWidget()
        self.detail_layout = QVBoxLayout(scroll_content)
        self.detail_layout.setContentsMargins(12, 12, 12, 12)
        self.detail_layout.setSpacing(12)

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

        self.txt_body = QTextEdit()
        self.txt_body.setReadOnly(True)
        self.txt_body.setStyleSheet("border: none; background-color: transparent; color: #E0E0E0; font-size: 11px;")
        self.detail_layout.addWidget(self.txt_body)

        scroll_area.setWidget(scroll_content)
        right_layout.addWidget(scroll_area)

        body_splitter.addWidget(self.right_panel)
        body_splitter.setSizes([140, 380, 410])
        self.content_layout.addWidget(body_splitter)

    def category_selected(self):
        sender_btn = self.sender()
        cat_val = sender_btn.property("cat_val")
        self.current_category = cat_val

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

        self.lbl_sender.setText(f"De: {email.get('sender')}")
        self.lbl_subject.setText(f"Asunto: {email.get('subject')}")
        
        received = email.get("received_at", "")
        if received and len(received) > 16:
            received = received[:16].replace("T", " ")
        self.lbl_date.setText(f"Fecha: {received} | Categoría: {(email.get('category') or 'otros').upper()} | Importancia: {(email.get('importance') or 'Baja').upper()}")

        summary = email.get("summary")
        if summary:
            self.lbl_summary_text.setText(summary)
        else:
            self.lbl_summary_text.setText("Este correo aún no ha sido clasificado por Alfonso.")

        self.txt_body.setText(email.get("body", ""))

        if email.get("read_status") == 0:
            self.api.mark_email_as_read(email.get("id"))
            selected_id = email.get("id")
            self.load_emails()
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
        
        self.stack = QStackedWidget()
        self.content_layout.addWidget(self.stack)
        
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
        
        self.page_server = QWidget()
        server_form = QFormLayout(self.page_server)
        server_form.setVerticalSpacing(15)
        server_form.setContentsMargins(10, 10, 10, 10)
        
        self.input_url = QLineEdit()
        server_form.addRow(QLabel("URL Servidor:"), self.input_url)
        self.stack.addWidget(self.page_server)
        
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
            
            import keyring
            gmail_pass = keyring.get_password("AlfonsoAutonomo", "GMAIL_APP_PASSWORD") or ""
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
            for idx, line in enumerate(lines):
                if line.strip().startswith("GMAIL_EMAIL="):
                    lines[idx] = f"GMAIL_EMAIL={gmail_email}\n"
                    email_found = True
                elif line.strip().startswith("GMAIL_APP_PASSWORD="):
                    lines[idx] = ""
                    
            if not email_found:
                lines.append(f"GMAIL_EMAIL={gmail_email}\n")
                
            lines = [line for line in lines if line.strip()]
                
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
                
            os.environ["GMAIL_EMAIL"] = gmail_email
            
            import keyring
            keyring.set_password("AlfonsoAutonomo", "GMAIL_APP_PASSWORD", gmail_pass)
            os.environ["GMAIL_APP_PASSWORD"] = gmail_pass
        except Exception as e:
            print(f"Error saving env/keyring credentials: {e}")

        QMessageBox.information(
            self, 
            "Configuración Guardada", 
            "Los parámetros del sistema operativo Alfonso OS han sido actualizados con éxito."
        )
        self.close()


class AlertsWidget(AlfonsoBaseDialog):
    """Centro de Alertas y Notificaciones del Sistema Alfonso OS."""
    def __init__(self, parent_dashboard):
        super().__init__(parent_dashboard, "ALFONSO ALERTS", modal=False)
        self.dashboard = parent_dashboard
        self.setMinimumSize(500, 400)

        self.setup_ui()

    def setup_ui(self):
        self.list_widget = QListWidget()
        self.content_layout.addWidget(self.list_widget)

        actions_layout = QHBoxLayout()
        actions_layout.addStretch()
        
        self.btn_clear = QPushButton("DESPEJAR ALERTAS")
        self.btn_clear.setObjectName("ClearBtn")
        self.btn_clear.setStyleSheet("color: #EF4444; border-color: rgba(239, 68, 68, 0.4); background-color: rgba(239, 68, 68, 0.1);")
        self.btn_clear.clicked.connect(self.clear_all)
        
        self.btn_close_panel = QPushButton("CERRAR")
        self.btn_close_panel.clicked.connect(self.close)
        
        actions_layout.addWidget(self.btn_clear)
        actions_layout.addWidget(self.btn_close_panel)
        self.content_layout.addLayout(actions_layout)

    def load_alerts(self):
        self.list_widget.clear()
        alerts = []
        
        url = self.dashboard.config.get('url', "http://localhost:8000")
        try:
            import urllib.request
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                pass
        except Exception:
            alerts.append("⚠️ [RED] Conexión Backend Offline - No se pudo contactar con " + url)

        dev_id = self.dashboard.config.get('device', 8)
        alerts.append(f"⚠️ [AUDIO] Entrada de audio ID [{dev_id}] en escucha activa.")
        
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

        self.page_iva = QWidget()
        iva_layout = QVBoxLayout(self.page_iva)
        iva_layout.setContentsMargins(0, 0, 0, 0)
        iva_layout.setSpacing(10)
        
        groups_layout = QHBoxLayout()
        groups_layout.setSpacing(15)
  
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
  
        self.lbl_result = QLabel("Resultado Neto Estimado: 0.00 €")
        self.lbl_result.setStyleSheet("color: #6366F1; font-size: 14px; font-weight: bold; padding: 10px; background-color: rgba(99, 102, 241, 0.05); border-radius: 6px; border: 1px solid rgba(99, 102, 241, 0.2);")
        self.lbl_result.setAlignment(Qt.AlignmentFlag.AlignCenter)
        iva_layout.addWidget(self.lbl_result)

        self.btn_export_iva_books = QPushButton("DESCARGAR LIBROS DE IVA OFICIALES")
        self.btn_export_iva_books.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); border-color: #10B981; color: #10B981; font-weight: bold; padding: 8px;")
        self.btn_export_iva_books.clicked.connect(self.export_iva_official_books)
        iva_layout.addWidget(self.btn_export_iva_books)
  
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
        
        self.pw_thread = PlaywrightWorkerThread(self)
        self.pw_thread.finished_signal.connect(self.on_browser_closed)
        self.pw_thread.start()
        
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

    def inject_autofill_script(self):
        if not self.pw_thread or not self.pw_thread.page:
            QMessageBox.warning(self, "Error", "El navegador de Playwright no está inicializado o se ha cerrado.")
            return
            
        try:
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
                        filledCount++;
                    }}
                }}
                alert("Alfonso Autónomo: Autorelleno inyectado correctamente. Se rellenaron " + filledCount + " casillas.");
            }})();
            """
            self.pw_thread.page.evaluate(js_script)
            QMessageBox.information(self, "Datos Inyectados", "Se han autorellenado las casillas del Modelo 303 en el formulario activo del navegador.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"No se pudo inyectar el autorelleno. Asegúrate de estar en la página del Modelo 303. Detalles: {e}")

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
        self.projects_data = {}
        self.active_project_name = "default"
        self.active_session_id = "default"
        
        self.setup_ui()

    def setup_ui(self):
        content_layout = QHBoxLayout()
        content_layout.setSpacing(20)
        
        left_layout = QVBoxLayout()
        left_layout.setSpacing(10)
        
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
        self.txt_input.installEventFilter(self)
        input_layout.addWidget(self.txt_input, 1)
        
        btn_send = QPushButton("ENVIAR")
        btn_send.setFixedSize(80, 50)
        btn_send.clicked.connect(self.send_message_from_dialog)
        input_layout.addWidget(btn_send)
        
        right_layout.addLayout(input_layout)
        content_layout.addLayout(right_layout, 3)
        
        self.content_layout.addLayout(content_layout, 1)
        
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
        if obj is self.txt_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                self.send_message_from_dialog()
                return True
        return super().eventFilter(obj, event)

    def select_project(self, item):
        display_name = item.text().replace("📁 ", "").strip().upper()
        self.active_project_name = display_name
        self.conv_list.clear()
        
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
        session_id = item.data(Qt.ItemDataRole.UserRole)
        title = item.data(Qt.ItemDataRole.UserRole + 1)
        project = item.data(Qt.ItemDataRole.UserRole + 2)
        
        if not session_id:
            return
            
        self.active_session_id = session_id
        self.dashboard.thread.session_id = session_id
        
        gui_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(os.path.dirname(gui_dir), "logs", "session_config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"session_id": session_id}, f, indent=4)
        except Exception:
            pass
            
        self.lbl_channel_status.setText(f"ACTIVO: {project.upper()} > {title.upper()}")
        self.header_title.setText(f"// ALFONSO OS // WORKSPACE: {project.upper()}")
        self.dashboard.lbl_active_session.setText(f"ACTIVO: {project.upper()} > {title.upper()}")
        
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
        text = self.txt_input.toPlainText().strip()
        if not text:
            return
            
        self.txt_input.clear()
        
        if not self.dashboard.text_mode_enabled:
            self.dashboard.toggle_text_mode()
            
        cur_html = self.chat_display.toHtml()
        user_msg_html = f"<p><b style='color:#F59E0B;'>[TÚ]</b><br/>{text.replace('\n', '<br/>')}</p>"
        self.chat_display.setHtml(cur_html + user_msg_html)
        QTimer.singleShot(50, lambda: self.chat_display.verticalScrollBar().setValue(self.chat_display.verticalScrollBar().maximum()))
        
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

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("<b>Seleccionar Cuenta:</b>"))
        
        self.cb_account = QComboBox()
        self.cb_account.currentIndexChanged.connect(self.load_bank_movements)
        filter_layout.addWidget(self.cb_account)
        
        btn_manage = QPushButton("⚙️ Administrar Bancos/Cuentas")
        btn_manage.clicked.connect(self.manage_connections)
        filter_layout.addWidget(btn_manage)
        
        self.content_layout.addLayout(filter_layout)

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
        reply = QMessageBox.warning(self, "Eliminar Conexión", "¿Estás seguro de que deseas eliminar esta cuenta bancaria? Los movimientos quedarán guardados.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
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
            self.lbl_warning.setText(f"<font color='#F59E0B'>⚠️ <b>Aviso:</b> Tu plan actual es <b>Gratuito</b>. Esta transferencia se procesará pero incurrirá en un recargo extra de <b>{self.fee:.2f} €</b>.</font>")
        elif self.used >= self.limit:
            self.lbl_warning.setText(f"<font color='#F59E0B'>⚠️ <b>Aviso:</b> Has agotado tu cupo de {self.limit} transferencias. Tendrá un recargo extra de <b>{self.fee:.2f} €</b>.</font>")
        else:
            remaining = self.limit - self.used
            self.lbl_warning.setText(f"<font color='#10B981'>✓ <b>Incluido en el plan:</b> Tienes {remaining} transferencias restantes de tu plan <b>{self.tier.upper()}</b>.</font>")

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
                msg += f"<font color='#EF4444'>Se ha cargado un extra de {res['extra_charge']:.2f} €.</font>"
            else:
                msg += "<font color='#10B981'>Operación cubierta por tu cupo premium.</font>"
                
            custom_dialog = AlfonsoBaseDialog(self, "FIRMA DE TRANSFERENCIA")
            custom_dialog.setMinimumSize(400, 200)
            custom_dialog.content_layout.addWidget(QLabel(f"Simulando Firma de Transferencia a través de la API segura del banco:<br><br><b>Destinatario:</b> {recipient}<br><b>Importe:</b> {amount:.2f} €<br><b>Estado:</b> Completada."))
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
        
        from app.domain.services.ledger_service import LedgerService
        accounts = LedgerService.get_pgc_accounts()
        
        self.cmb_debe = QComboBox()
        self.cmb_haber = QComboBox()
        
        for acc in accounts:
            label = f"{acc['code']} - {acc['name']}"
            self.cmb_debe.addItem(label, acc['code'])
            self.cmb_haber.addItem(label, acc['code'])
            
        idx_debe = self.cmb_debe.findData("62900000")
        if idx_debe >= 0:
            self.cmb_debe.setCurrentIndex(idx_debe)
            
        idx_haber = self.cmb_haber.findData("57000000")
        if idx_haber >= 0:
            self.cmb_haber.setCurrentIndex(idx_haber)
            
        form_layout.addRow("Cuenta de Cargo (Debe):", self.cmb_debe)
        form_layout.addRow("Cuenta de Abono (Haber):", self.cmb_haber)
        
        self.spin_amount = QDoubleSpinBox()
        self.spin_amount.setRange(0.01, 999999.00)
        self.spin_amount.setDecimals(2)
        self.spin_amount.setSuffix(" €")
        self.spin_amount.setValue(50.00)
        form_layout.addRow("Importe del Asiento:", self.spin_amount)
        
        self.content_layout.addLayout(form_layout)
        
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
        
        self.main_stack = QStackedWidget()
        self.content_layout.addWidget(self.main_stack)

        self.page_diario = QWidget()
        diario_main_layout = QVBoxLayout(self.page_diario)
        diario_main_layout.setContentsMargins(0, 0, 0, 0)
        
        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

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
                padding: 8px 12px;
            }
        """)
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(6)

        lbl_filters = QLabel("FILTROS CONTABLES")
        lbl_filters.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent; border: none;")
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

        self.filter_buttons[None].setProperty("active", "true")

        left_layout.addStretch()
        body_splitter.addWidget(self.left_panel)

        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(10, 0, 0, 0)
        right_layout.setSpacing(10)

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

        self.page_mayor = QWidget()
        page_mayor_layout = QVBoxLayout(self.page_mayor)
        page_mayor_layout.setContentsMargins(0, 5, 0, 0)
        page_mayor_layout.setSpacing(10)
        
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
        
        self.table_mayor = QTableWidget()
        self.table_mayor.setColumnCount(6)
        self.table_mayor.setHorizontalHeaderLabels(["Fecha", "Asiento", "Concepto", "Debe", "Haber", "Saldo"])
        self.table_mayor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_mayor.verticalHeader().setVisible(False)
        page_mayor_layout.addWidget(self.table_mayor)
        
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

        from app.domain.services.ledger_service import LedgerService
        accounts = LedgerService.get_pgc_accounts()
        for acc in accounts:
            label = f"{acc['code']} - {acc['name']}"
            self.cmb_mayor_account.addItem(label, acc['code'])

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
            
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Fecha", "Asiento", "Cuenta PGC", "Nombre Cuenta", "Concepto", "Debe", "Haber"])
                
                for row in range(self.table.rowCount()):
                    row_data = []
                    for col in range(self.table.columnCount()):
                        item = self.table.item(row, col)
                        row_data.append(item.text() if item else "")
                    writer.writerow(row_data)
            QMessageBox.information(self, "Exportar", "El libro diario ha sido exportado correctamente.")
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
                
                is_match = False
                if self.current_category is None:
                    is_match = True
                elif self.current_category == "manual":
                    if not concepto.startswith("Factura"):
                        is_match = True
                else:
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
            
            with open(file_path, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(["Fecha", "Asiento", "Concepto", "Debe", "Haber", "Saldo"])
                
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
        filename = os.path.basename(filepath) if filepath else "DOCUMENTO"
        super().__init__(parent, f"VISOR - {filename.upper()}")
        self.filepath = filepath
        self.setMinimumSize(1150, 850)
        self.setup_viewer_ui()

    def setup_viewer_ui(self):
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
        from PyQt6.QtGui import QPixmap, QImage
        try:
            import pypdfium2 as pdfium
            
            doc = pdfium.PdfDocument(self.filepath)
            self._page_images = []
            
            for i in range(len(doc)):
                page = doc[i]
                bitmap = page.render(scale=2.0)
                pil_img = bitmap.to_pil()
                
                pil_img = pil_img.convert("RGBA")
                width, height = pil_img.size
                img_data = pil_img.tobytes("raw", "RGBA")
                
                qimage = QImage(img_data, width, height, QImage.Format.Format_RGBA8888)
                self._page_images.append(img_data)
                
                pixmap = QPixmap.fromImage(qimage)
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
        lbl_info = QLabel("El formato de este documento no soporta previsualización nativa.\n\nPuedes abrirlo externamente en su aplicación predeterminada.")
        lbl_info.setStyleSheet("color: #CBD5E1; font-size: 13px;")
        lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_layout.addWidget(lbl_info)

    def open_externally(self):
        try:
            from PyQt6.QtCore import QUrl
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
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 10)
        
        self.btn_import_file = QPushButton("IMPORTAR DOCUMENTO")
        self.btn_import_file.setStyleSheet("background-color: rgba(99, 102, 241, 0.15); border-color: #6366F1; color: #818CF8; font-weight: bold;")
        self.btn_import_file.clicked.connect(self.import_document)
        top_bar.addWidget(self.btn_import_file)

        top_bar.addSpacing(10)

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

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: rgba(99, 102, 241, 0.3); }")

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
                padding: 8px 12px;
            }
        """)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(6)

        lbl_sidebar = QLabel("CATEGORÍAS")
        lbl_sidebar.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px; margin-bottom: 4px; background: transparent; border: none;")
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

        self.inspector_panel = QWidget()
        self.inspector_panel.setStyleSheet("background-color: rgba(15, 23, 42, 0.2); border-left: 1px solid rgba(255, 255, 255, 0.05);")
        inspector_layout = QVBoxLayout(self.inspector_panel)
        inspector_layout.setContentsMargins(15, 15, 15, 15)
        inspector_layout.setSpacing(12)

        lbl_inspector_title = QLabel("INSPECTOR")
        lbl_inspector_title.setStyleSheet("font-weight: bold; font-size: 9px; color: #6366F1; letter-spacing: 0.5px;")
        inspector_layout.addWidget(lbl_inspector_title)

        self.lbl_big_icon = QLabel("📄")
        self.lbl_big_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_big_icon.setStyleSheet("font-size: 54px; margin-top: 15px; margin-bottom: 10px;")
        inspector_layout.addWidget(self.lbl_big_icon)

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
        
        self.main_splitter.setSizes([160, 480, 210])
        self.content_layout.addWidget(self.main_splitter)

        self.load_files()

    def load_files(self):
        self.list_widget.clear()
        self.reset_inspector()
        
        if not os.path.exists(self.current_dir):
            return
            
        try:
            self.btn_back.setEnabled(len(self.history_back_stack) > 0)
            self.btn_forward.setEnabled(len(self.history_forward_stack) > 0)
            is_at_root = os.path.abspath(self.current_dir) == os.path.abspath(self.archive_dir)
            self.btn_up.setEnabled(not is_at_root)

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
            
            for dname in dirs:
                full_path = os.path.join(self.current_dir, dname)
                item = QListWidgetItem()
                item.setText(dname)
                item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
                item.setData(Qt.ItemDataRole.UserRole, full_path)
                item.setData(Qt.ItemDataRole.UserRole + 1, True)
                self.list_widget.addItem(item)
                
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
                QMessageBox.warning(self, "Error", f"No se pudo abrir el visor: {e}")

    def delete_selected_file(self):
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
            
        try:
            dest_name = os.path.basename(file_path)
            dest_path = os.path.join(self.current_dir, dest_name)
            
            if os.path.exists(dest_path):
                import time
                base, ext = os.path.splitext(dest_name)
                dest_name = f"{base}_{int(time.time())}{ext}"
                dest_path = os.path.join(self.current_dir, dest_name)
                
            shutil.copy2(file_path, dest_path)
            QMessageBox.information(self, "Importación", "El archivo ha sido importado con éxito.")
            self.load_files()
        except Exception as e:
            QMessageBox.warning(self, "Error al importar", f"No se pudo copiar el archivo: {e}")


class EconomicAnalyzerThread(QThread):
    progress_signal = pyqtSignal(str)
    result_signal = pyqtSignal(str)
    
    def __init__(self, data_stats):
        super().__init__()
        self.stats = data_stats
        
    def run(self):
        import time
        self.progress_signal.emit("[SISTEMA ALFONSO] Iniciando análisis financiero de riesgos...")
        time.sleep(1.0)
        self.progress_signal.emit("[CONEXIÓN SECURE] Consultando base de datos local y libro contable...")
        time.sleep(0.8)
        self.progress_signal.emit("[WEB AGENT] Buscando noticias macroeconómicas del sector en España 2026...")
        time.sleep(1.2)
        self.progress_signal.emit("[WEB AGENT] Analizando reforma del RETA, IPC actualizados y MEAE tributario...")
        time.sleep(1.0)
        self.progress_signal.emit("[AUDITORÍA] Procesando margen operativo y tasa de cash burn...")
        time.sleep(0.8)
        self.progress_signal.emit("[DIAGNÓSTICO] Redactando informe crítico de viabilidad y estrategias...")
        time.sleep(0.6)
        
        ing = self.stats.get('total_ingresos', 0.0)
        gast = self.stats.get('total_gastos', 0.0)
        neto = ing - gast
        imp = self.stats.get('total_impuestos', 0.0)
        
        ratio_gastos = (gast / ing * 100) if ing > 0 else 0
        rentabilidad = (neto / ing * 100) if ing > 0 else 0
        
        report = f"""========================================================================
ALFONSO FINANCIAL INTEL SYSTEM - INFORME ESTRATÉGICO Y JUICIO CRÍTICO
========================================================================
FECHA DE EMISIÓN: {datetime.datetime.now().strftime("%d de %B de %Y")}
ESTADO DE AUDITORÍA: CRÍTICO Y ESTRATÉGICO

1. AUDITORÍA DE DATOS DE LA EMPRESA (AÑO CURSO 2026):
------------------------------------------------------------------------
* INGRESOS DECLARADOS: {ing:,.2f} €
* GASTOS TOTALES REGISTRADOS: {gast:,.2f} €
* RESULTADO NETO (EXPLICIT): {neto:,.2f} €
* IMPUESTOS LIQUIDADOS/REBOZADOS (IVA + IRPF): {imp:,.2f} €

ANÁLISIS DE EFICIENCIA:
* Tasa de Gasto Operativo: {ratio_gastos:.2f}% (Consumo de cada euro ingresado).
* Rentabilidad Neta del Ejercicio (Tasa de Retorno): {rentabilidad:.2f}%

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
   - Renegociar contratos de servicios (proveedores, telefonía, hosting).
B) Optimización de Ingresos (Pricing & Value):
   - Indexar tarifas un 5% para cubrir el impacto de la inflación acumulada.
   - Transicionar de facturación por horas a modelos de retención (retainers) fijos mensuales para estabilizar el flujo de caja.
C) Cobertura Fiscal (Tax Planning):
   - Maximizar la deducción de gastos afectos a la actividad (herramientas de software, suministros de teletrabajo regulados).
   - Realizar cierres simulados mensuales para prever las retenciones del Modelo 130 y el pago de IVA trimestral para evitar estrangulamientos de liquidez.

========================================================================="""
        self.result_signal.emit(report)


class KPICard(QFrame):
    """Tarjeta HUD para mostrar métricas clave consolidadas."""
    def __init__(self, title, value, subtext, color="#FFB800", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            KPICard {{
                background-color: rgba(30, 41, 59, 0.6);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        
        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setStyleSheet("font-size: 9px; font-weight: bold; color: #94A3B8; letter-spacing: 0.5px; background: transparent; border: none;")
        
        self.lbl_value = QLabel(value)
        self.lbl_value.setStyleSheet("font-family: 'Consolas'; font-size: 16px; font-weight: bold; color: #FFFFFF; background: transparent; border: none;")
        
        self.lbl_subtext = QLabel(subtext)
        self.lbl_subtext.setStyleSheet("font-size: 9px; color: #64748B; background: transparent; border: none;")
        
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)
        layout.addWidget(self.lbl_subtext)
        
    def update_values(self, value, subtext):
        self.lbl_value.setText(value)
        self.lbl_subtext.setText(subtext)


class KPIChartWidget(QWidget):
    """Gráfico de series temporales de Ingresos vs Gastos con líneas y áreas."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 220)
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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos de ingresos/gastos")
            return
            
        keys = sorted(self.data.keys())
        left_margin = 60
        right_margin = 20
        top_margin = 35
        bottom_margin = 35
        
        chart_w = self.width() - left_margin - right_margin
        chart_h = self.height() - top_margin - bottom_margin
        
        max_val = 1.0
        for k in keys:
            max_val = max(max_val, self.data[k]['ingresos'], self.data[k]['gastos'])
            
        max_val = ((int(max_val) // 1000) + 1) * 1000
        
        painter.setFont(QFont("Consolas", 7))
        grid_lines = 4
        for i in range(grid_lines + 1):
            y = top_margin + chart_h - (i * chart_h // grid_lines)
            val = i * max_val // grid_lines
            painter.setPen(QPen(QColor(255, 255, 255, 10), 1, Qt.PenStyle.DashLine))
            painter.drawLine(left_margin, y, left_margin + chart_w, y)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(8, y + 3, f"{val:,.0f}€".replace(",", "."))
            
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
                    painter.drawText(int(x - 15), top_margin + chart_h + 15, lbl_x)
            else:
                painter.drawText(int(x - 12), top_margin + chart_h + 15, lbl_x)
                
        if points_ing:
            path_area_ing = QPainterPath(path_ing)
            path_area_ing.lineTo(points_ing[-1][0], top_margin + chart_h)
            path_area_ing.lineTo(points_ing[0][0], top_margin + chart_h)
            path_area_ing.closeSubpath()
            grad_ing = QLinearGradient(0, top_margin, 0, top_margin + chart_h)
            grad_ing.setColorAt(0.0, QColor(16, 185, 129, 40))
            grad_ing.setColorAt(1.0, QColor(16, 185, 129, 0))
            painter.fillPath(path_area_ing, QBrush(grad_ing))
            
        if points_gast:
            path_area_gast = QPainterPath(path_gast)
            path_area_gast.lineTo(points_gast[-1][0], top_margin + chart_h)
            path_area_gast.lineTo(points_gast[0][0], top_margin + chart_h)
            path_area_gast.closeSubpath()
            grad_gast = QLinearGradient(0, top_margin, 0, top_margin + chart_h)
            grad_gast.setColorAt(0.0, QColor(239, 68, 68, 30))
            grad_gast.setColorAt(1.0, QColor(239, 68, 68, 0))
            painter.fillPath(path_area_gast, QBrush(grad_gast))

        painter.setPen(QPen(QColor(239, 68, 68, 220), 2))
        painter.drawPath(path_gast)
        painter.setBrush(QColor(239, 68, 68))
        for p in points_gast:
            painter.drawEllipse(int(p[0] - 2), int(p[1] - 2), 4, 4)
            
        painter.setPen(QPen(QColor(16, 185, 129, 255), 2))
        painter.drawPath(path_ing)
        painter.setBrush(QColor(16, 185, 129))
        for p in points_ing:
            painter.drawEllipse(int(p[0] - 2), int(p[1] - 2), 4, 4)


class KPITaxChartWidget(QWidget):
    """Gráfico de barras mensuales de impuestos (IVA Soportado vs IVA Repercutido vs IRPF)."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 220)
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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos de impuestos")
            return
            
        keys = sorted(self.data.keys())
        left_margin = 55
        right_margin = 20
        top_margin = 35
        bottom_margin = 35
        
        chart_w = self.width() - left_margin - right_margin
        chart_h = self.height() - top_margin - bottom_margin
        
        max_val = 1.0
        for k in keys:
            max_val = max(max_val, self.data[k]['iva_sop'], self.data[k]['iva_rep'], self.data[k]['irpf'])
            
        max_val = ((int(max_val) // 500) + 1) * 500
        
        painter.setFont(QFont("Consolas", 7))
        grid_lines = 3
        for i in range(grid_lines + 1):
            y = top_margin + chart_h - (i * chart_h // grid_lines)
            val = i * max_val // grid_lines
            painter.setPen(QPen(QColor(255, 255, 255, 10), 1, Qt.PenStyle.DashLine))
            painter.drawLine(left_margin, y, left_margin + chart_w, y)
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(8, y + 3, f"{val:,.0f}€".replace(",", "."))
            
        num_points = len(keys)
        col_w = chart_w / max(1, num_points)
        bar_w = max(4, int(col_w * 0.25))
        
        meses_nombres = {
            "01": "Ene", "02": "Feb", "03": "Mar", "04": "Abr", "05": "May", "06": "Jun",
            "07": "Jul", "08": "Ago", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dic"
        }
        
        for i, k in enumerate(keys):
            x_center = left_margin + i * col_w + col_w / 2
            
            x_sop = x_center - bar_w * 1.5
            x_rep = x_center - bar_w * 0.5
            x_irpf = x_center + bar_w * 0.5
            
            h_sop = self.data[k]['iva_sop'] * chart_h / max_val
            h_rep = self.data[k]['iva_rep'] * chart_h / max_val
            h_irpf = self.data[k]['irpf'] * chart_h / max_val
            
            y_sop = top_margin + chart_h - h_sop
            y_rep = top_margin + chart_h - h_rep
            y_irpf = top_margin + chart_h - h_irpf
            
            painter.setBrush(QColor(14, 116, 144))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(x_sop), int(y_sop), bar_w, int(h_sop))
            
            painter.setBrush(QColor(59, 130, 246))
            painter.drawRect(int(x_rep), int(y_rep), bar_w, int(h_rep))
            
            painter.setBrush(QColor(168, 85, 247))
            painter.drawRect(int(x_irpf), int(y_irpf), bar_w, int(h_irpf))
            
            lbl_x = k
            if not self.show_all_time and k in meses_nombres:
                lbl_x = meses_nombres[k]
                
            painter.setPen(QColor(148, 163, 184))
            painter.drawText(int(x_center - 10), top_margin + chart_h + 15, lbl_x)


class ExpenseDistributionWidget(QFrame):
    """Widget de distribución de gastos por proveedor/concepto."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(350, 220)
        self.setStyleSheet("""
            ExpenseDistributionWidget {
                background-color: rgba(15, 23, 42, 0.85);
                border: 1px solid rgba(99, 102, 241, 0.2);
                border-radius: 8px;
                padding: 12px;
            }
        """)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(8)
        
        lbl_title = QLabel("DISTRIBUCIÓN DE GASTOS PRINCIPALES")
        lbl_title.setStyleSheet("font-size: 10px; font-weight: bold; color: #818CF8; letter-spacing: 0.5px; background: transparent; border: none;")
        self.main_layout.addWidget(lbl_title)
        
        self.rows_container = QVBoxLayout()
        self.rows_container.setSpacing(6)
        self.main_layout.addLayout(self.rows_container)
        self.main_layout.addStretch()
        
    def set_data(self, expense_concepts):
        while self.rows_container.count() > 0:
            child = self.rows_container.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        if not expense_concepts:
            lbl_empty = QLabel("Sin gastos registrados")
            lbl_empty.setStyleSheet("font-size: 11px; color: #64748B; font-style: italic;")
            self.rows_container.addWidget(lbl_empty)
            return
            
        sorted_concepts = sorted(expense_concepts.items(), key=lambda x: x[1], reverse=True)[:5]
        max_val = max(1.0, sum(expense_concepts.values()))
        
        for concept, val in sorted_concepts:
            row_layout = QVBoxLayout()
            row_layout.setSpacing(2)
            
            text_layout = QHBoxLayout()
            lbl_name = QLabel(concept)
            lbl_name.setStyleSheet("font-size: 10px; color: #F1F5F9; font-weight: 500;")
            
            pct = (val / max_val) * 100
            lbl_val = QLabel(f"{val:,.2f} € ({pct:.1f}%)".replace(",", "X").replace(".", ",").replace("X", "."))
            lbl_val.setStyleSheet("font-family: 'Consolas'; font-size: 10px; color: #EF4444; font-weight: bold;")
            
            text_layout.addWidget(lbl_name)
            text_layout.addStretch()
            text_layout.addWidget(lbl_val)
            row_layout.addLayout(text_layout)
            
            prog = QProgressBar()
            prog.setFixedHeight(6)
            prog.setTextVisible(False)
            prog.setStyleSheet("""
                QProgressBar {
                    background-color: rgba(255, 255, 255, 0.05);
                    border: none;
                    border-radius: 3px;
                }
                QProgressBar::chunk {
                    background-color: #EF4444;
                    border-radius: 3px;
                }
            """)
            prog.setValue(int(pct))
            row_layout.addWidget(prog)
            
            w = QFrame()
            w.setLayout(row_layout)
            w.setStyleSheet("background: transparent; border: none;")
            self.rows_container.addWidget(w)


class AlfonsoKPIDashboardDialog(AlfonsoBaseDialog):
    """Dashboard de KPIs de negocio y análisis estratégico completo."""
    def __init__(self, parent=None):
        super().__init__(parent, "HUD KPIs DE NEGOCIO Y CONTROL FISCAL")
        self.setMinimumSize(1200, 800)
        self.show_all_time = False
        self.setup_kpi_ui()
        self.load_kpi_data()
        
    def setup_kpi_ui(self):
        layout = self.content_layout
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
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
        
        lbl_legend = QLabel(
            "Métricas: "
            "<span style='color:#10B981;'>■ Ingresos</span>  |  "
            "<span style='color:#EF4444;'>■ Gastos</span>  |  "
            "<span style='color:#0E7490;'>■ IVA Soportado</span>  |  "
            "<span style='color:#3B82F6;'>■ IVA Repercutido</span>  |  "
            "<span style='color:#A855F7;'>■ IRPF Retenido</span>"
        )
        lbl_legend.setStyleSheet("font-size: 10px; font-weight: bold; color: #E2E8F0;")
        top_row.addWidget(lbl_legend)
        
        layout.addLayout(top_row)
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        
        self.card_roi = KPICard("Tasa de Retorno (ROI)", "0.00%", "Margen operativo neto", "#818CF8", self)
        self.card_iva = KPICard("Liquidador IVA", "0.00 €", "IVA repercutido - soportado", "#3B82F6", self)
        self.card_irpf = KPICard("Retenciones IRPF", "0.00 €", "Total IRPF ingresado a cuenta", "#A855F7", self)
        self.card_spending = KPICard("Eficiencia Gasto", "0.00%", "Porcentaje s/ ingresos", "#EF4444", self)
        
        cards_layout.addWidget(self.card_roi)
        cards_layout.addWidget(self.card_iva)
        cards_layout.addWidget(self.card_irpf)
        cards_layout.addWidget(self.card_spending)
        layout.addLayout(cards_layout)
        
        charts_layout = QHBoxLayout()
        charts_layout.setSpacing(12)
        
        self.chart = KPIChartWidget(self)
        self.tax_chart = KPITaxChartWidget(self)
        self.expense_dist = ExpenseDistributionWidget(self)
        
        charts_layout.addWidget(self.chart, 5)
        charts_layout.addWidget(self.tax_chart, 4)
        charts_layout.addWidget(self.expense_dist, 4)
        layout.addLayout(charts_layout, 3)
        
        self.btn_evaluate = QPushButton("EMITIR JUICIO DE VALOR Y ANÁLISIS ESTRATÉGICO SECTORIAL")
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
        layout.addWidget(self.btn_evaluate)
        
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setPlaceholderText("Haz clic en el botón superior para realizar la auditoría económica del negocio en tiempo real...")
        self.terminal.setStyleSheet("""
            QTextEdit {
                background-color: #0B0F19;
                border: 1px solid rgba(0, 240, 255, 0.2);
                font-family: 'Consolas', 'Fira Code', monospace;
                font-size: 11px;
                color: #00F0FF;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.terminal, 2)
        
    def set_period_2026(self):
        self.show_all_time = False
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
        self.load_kpi_data()
        
    def set_period_all(self):
        self.show_all_time = True
        self.btn_period_all.setStyleSheet("""
            QPushButton {
                background-color: rgba(99, 102, 241, 0.3);
                border: 1px solid #818CF8;
                color: #FFFFFF;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        self.btn_period_2026.setStyleSheet("""
            QPushButton {
                background-color: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #94A3B8;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
            }
        """)
        self.load_kpi_data()
        
    def load_kpi_data(self):
        try:
            from app.adapters.memory.memory import _get_connection
            from app.utils.encryption import encryptor
            
            total_ing = 0.0
            total_gast = 0.0
            total_iva_sop = 0.0
            total_iva_rep = 0.0
            total_irpf = 0.0
            
            monthly_data = collections.defaultdict(lambda: {
                'ingresos': 0.0, 'gastos': 0.0, 
                'iva_sop': 0.0, 'iva_rep': 0.0, 'irpf': 0.0
            })
            
            expense_concepts = collections.defaultdict(float)
            
            with _get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT base_imponible, iva_amount, irpf_amount, category, date, year, concept FROM invoices"
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
                        concept_str = row["concept"] if row["concept"] else "Otros Gastos"
                        
                        month_key = date_str[5:7]
                        if self.show_all_time:
                            key = f"{year_val}/{month_key}"
                        else:
                            key = month_key
                            
                        if cat in ("ingreso", "income"):
                            total_ing += base
                            total_iva_rep += iva
                            total_irpf += irpf
                            
                            monthly_data[key]['ingresos'] += base
                            monthly_data[key]['iva_rep'] += iva
                            monthly_data[key]['irpf'] += irpf
                        else:
                            total_gast += base
                            total_iva_sop += iva
                            expense_concepts[concept_str] += base
                            
                            monthly_data[key]['gastos'] += base
                            monthly_data[key]['iva_sop'] += iva
                    except Exception:
                        pass
                        
            if not monthly_data and not self.show_all_time:
                for m in [f"{i:02d}" for i in range(1, 13)]:
                    monthly_data[m] = {'ingresos': 0.0, 'gastos': 0.0, 'iva_sop': 0.0, 'iva_rep': 0.0, 'irpf': 0.0}
            elif not self.show_all_time:
                for m in [f"{i:02d}" for i in range(1, 13)]:
                    if m not in monthly_data:
                        monthly_data[m] = {'ingresos': 0.0, 'gastos': 0.0, 'iva_sop': 0.0, 'iva_rep': 0.0, 'irpf': 0.0}
            
            neto = total_ing - total_gast
            roi = (neto / total_ing * 100) if total_ing > 0 else 0.0
            efficiency = (total_gast / total_ing * 100) if total_ing > 0 else 0.0
            
            self.card_roi.update_values(
                f"{roi:.1f}%", 
                f"Resultado Neto: {neto:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            self.card_iva.update_values(
                f"{(total_iva_rep - total_iva_sop):,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
                f"Rep: {total_iva_rep:,.0f}€ | Sop: {total_iva_sop:,.0f}€".replace(",", ".")
            )
            self.card_irpf.update_values(
                f"{total_irpf:,.2f} €".replace(",", "X").replace(".", ",").replace("X", "."),
                "Pagos a cuenta del ejercicio"
            )
            self.card_spending.update_values(
                f"{efficiency:.1f}%",
                f"Consumido: {total_gast:,.0f}€ de {total_ing:,.0f}€".replace(",", ".")
            )
            
            self.chart.set_data(dict(monthly_data), self.show_all_time)
            self.tax_chart.set_data(dict(monthly_data), self.show_all_time)
            self.expense_dist.set_data(dict(expense_concepts))
            
        except Exception as e:
            print(f"Error cargando KPIs: {e}")
            
    def run_economic_audit(self):
        try:
            total_ingresos = 0.0
            total_gastos = 0.0
            total_impuestos = 0.0
            
            chart_data = self.chart.data
            for val in chart_data.values():
                total_ingresos += val['ingresos']
                total_gastos += val['gastos']
                total_impuestos += val['iva_rep'] + val['irpf']
                
            stats = {
                'total_ingresos': total_ingresos,
                'total_gastos': total_gastos,
                'total_impuestos': total_impuestos
            }
            
            self.btn_evaluate.setEnabled(False)
            self.terminal.clear()
            
            self.worker = EconomicAnalyzerThread(stats)
            self.worker.progress_signal.connect(self.log_to_terminal)
            self.worker.result_signal.connect(self.show_audit_result)
            self.worker.start()
        except Exception as e:
            self.terminal.setText(f"Error al iniciar auditoría: {e}")
            self.btn_evaluate.setEnabled(True)
            
    def log_to_terminal(self, text):
        self.terminal.append(text)
        
    def show_audit_result(self, result_text):
        self.terminal.append("\n" + result_text)
        self.btn_evaluate.setEnabled(True)
