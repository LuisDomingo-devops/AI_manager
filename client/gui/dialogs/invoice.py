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
                             QDoubleSpinBox, QButtonGroup, QProgressBar, QListView, QStyle, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QEvent
from PyQt6.QtGui import QColor, QFont, QPixmap, QDesktopServices, QPainter, QPen, QBrush, QLinearGradient, QPainterPath
from core.api_client import AlfonsoAPI
from client.gui.dialogs.base import AlfonsoBaseDialog

class AlfonsoInvoiceConfirmDialog(QDialog):
    """Diálogo popup para la confirmación humana obligatoria antes de emitir una factura firme."""
    def __init__(self, parent, invoice_data):
        super().__init__(parent)
        self.setWindowTitle("CONFIRMACIÓN DE EMISIÓN DE FACTURA (VERI*FACTU)")
        self.setMinimumSize(450, 320)
        self.setStyleSheet("background-color: #0F172A; color: #E2E8F0; font-family: 'Segoe UI', sans-serif;")
        
        self.invoice_data = invoice_data
        self.confirmed = False
        
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("REVISIÓN PREVIA FISCAL REGLAMENTARIA")
        title.setStyleSheet("color: #F59E0B; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        desc = QLabel(
            "De acuerdo con el Real Decreto 1007/2023, la emisión de esta factura generará un registro local "
            "inalterable y se remitirá a la AEAT (Veri*Factu). Por favor, confirme que los datos son correctos:"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 11px; color: #94A3B8;")
        layout.addWidget(desc)

        # Detalles en un GroupBox
        group = QGroupBox("Datos del Registro")
        group.setStyleSheet("QGroupBox { border: 1px solid rgba(245, 158, 11, 40); border-radius: 4px; margin-top: 10px; padding-top: 10px; } QGroupBox::title { color: #F59E0B; subcontrol-origin: margin; left: 10px; }")
        grid = QFormLayout()
        grid.setSpacing(6)
        
        lbl_cliente = QLabel(self.invoice_data.get("client_name", "Desconocido"))
        lbl_cliente.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        grid.addRow("Cliente:", lbl_cliente)
        
        lbl_nif = QLabel(self.invoice_data.get("client_nif", "Desconocido"))
        lbl_nif.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        grid.addRow("NIF:", lbl_nif)

        lbl_concepto = QLabel(self.invoice_data.get("concept", "Desconocido"))
        lbl_concepto.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        grid.addRow("Concepto:", lbl_concepto)
        
        total = float(self.invoice_data.get("amount", 0.0))
        iva_rate = float(self.invoice_data.get("iva_rate", 21.0))
        iva_amount = total * (iva_rate / 100.0)
        total_amount = total + iva_amount
        
        lbl_base = QLabel(f"{total:,.2f} €")
        lbl_base.setStyleSheet("font-weight: bold; color: #F8FAFC;")
        grid.addRow("Base Imponible:", lbl_base)

        lbl_total = QLabel(f"{total_amount:,.2f} € (IVA {iva_rate}% incl.)")
        lbl_total.setStyleSheet("font-weight: bold; color: #10B981; font-size: 12px;")
        grid.addRow("Importe Total:", lbl_total)

        group.setLayout(grid)
        layout.addWidget(group)

        # Botones de Acción
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        btn_cancel = QPushButton("Guardar como Borrador")
        btn_cancel.setStyleSheet("background-color: rgba(148, 163, 184, 0.15); border: 1px solid #64748B; color: #94A3B8; height: 32px; font-weight: bold;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_confirm = QPushButton("Confirmar y Registrar (AEAT)")
        btn_confirm.setStyleSheet("background-color: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; color: #34D399; height: 32px; font-weight: bold;")
        btn_confirm.clicked.connect(self.confirm_invoice)
        btn_layout.addWidget(btn_confirm)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def confirm_invoice(self):
        self.confirmed = True
        self.accept()


class CalendarWidget(AlfonsoBaseDialog):
    """Interfaz gráfica nativa para el Calendario de Alfonso (ALFONSO OS)."""
    def __init__(self, api_client, parent=None, embedded=False):
        super().__init__(parent, "ALFONSO CALENDAR", modal=False, embedded=embedded)
        self.api = api_client
        if not embedded:
            self.setMinimumSize(850, 580)

        # Fechas operativas
        now = datetime.datetime.now()
        self.current_year = now.year
        self.current_month = now.month
        self.selected_date = now.strftime("%Y-%m-%d")
        
        self.events_cache = {}

        self.setup_ui()
        self.load_events()

    def setup_ui(self):
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)

        left_panel = QVBoxLayout()
        
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

        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        
        days = ["LUN", "MAR", "MIE", "JUE", "VIE", "SAB", "DOM"]
        for idx, day in enumerate(days):
            lbl = QLabel(day)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("font-weight: bold; color: #6366F1; font-size: 11px; padding: 5px;")
            self.grid_layout.addWidget(lbl, 0, idx)

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

        divider = QFrame()
        divider.setObjectName("Separator")
        divider.setFrameShape(QFrame.Shape.VLine)
        content_layout.addWidget(divider)

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
                dt = ev.get("start_time", "")[:10]
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
        
        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(0, 0, 0, 0)
        
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
        
        lbl_sub = QLabel(subject, self)
        sub_color = "#F8FAFC" if read == 0 else "#64748B"
        lbl_sub.setStyleSheet(f"font-size: 10px; color: {sub_color}; background: transparent;")
        lbl_sub.setWordWrap(False)
        layout.addWidget(lbl_sub)
