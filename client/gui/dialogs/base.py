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

class AlfonsoBaseDialog(QDialog):
    """
    Clase base para todos los diálogos/ventanas de Alfonso.
    Asegura consistencia visual (estilo CRT retro / cyberpunk) y facilita cambios globales de apariencia.
    """
    def __init__(self, parent=None, title="SISTEMA ALFONSO", modal=False, embedded=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(modal)
        self.embedded = embedded
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        else:
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_base_ui(title)
        if embedded:
            if hasattr(self, 'title_bar'): self.title_bar.hide()
            if hasattr(self, 'btn_minimize'): self.btn_minimize.hide()
            if hasattr(self, 'btn_close'): self.btn_close.hide()
            self.setStyleSheet("""
                #OuterFrame {
                    background-color: transparent;
                    border: none;
                }
            """)
        else:
            self.apply_base_stylesheet()
        self.drag_position = None

    def mousePressEvent(self, event):
        if not getattr(self, 'embedded', False) and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if not getattr(self, 'embedded', False) and event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_position') and self.drag_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if not getattr(self, 'embedded', False):
            self.drag_position = None

    def setup_base_ui(self, title):
        self.base_layout = QVBoxLayout(self)
        self.base_layout.setContentsMargins(0, 0, 0, 0)
        self.base_layout.setSpacing(0)

        self.outer_frame = QFrame(self)
        self.outer_frame.setObjectName("OuterFrame")
        self.outer_layout = QVBoxLayout(self.outer_frame)
        self.outer_layout.setContentsMargins(12, 12, 12, 12)
        self.outer_layout.setSpacing(10)

        self.title_bar = QFrame(self.outer_frame)
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(35)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(10, 0, 10, 0)

        self.header_title = QLabel(self.title_bar)
        self.header_title.setObjectName("TitleLabel")
        self.header_title.setText(f'<span style="color:#6366F1; font-size:12px;">●</span> &nbsp;<span style="font-size:11px; font-weight:bold; letter-spacing:1px; color:#F1F5F9;">{title.upper()}</span>')
        self.title_layout.addWidget(self.header_title)
        self.title_layout.addStretch()

        # Importación tardía para evitar Circular Dependency
        from client.gui.app import AlfonsoWindowMinimizeButton, AlfonsoWindowCloseButton
        
        self.btn_minimize = AlfonsoWindowMinimizeButton(self.title_bar)
        self.btn_minimize.clicked.connect(self.showMinimized)
        self.title_layout.addWidget(self.btn_minimize)

        self.btn_close = AlfonsoWindowCloseButton(self.title_bar)
        self.btn_close.clicked.connect(self.close)
        self.title_layout.addWidget(self.btn_close)

        self.outer_layout.addWidget(self.title_bar)

        self.content_widget = QWidget(self.outer_frame)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
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


class AlfonsoComplianceDialog(AlfonsoBaseDialog):
    """Diálogo para consultar la Declaración Responsable de Conformidad (Real Decreto 1007/2023)."""
    def __init__(self, parent=None, embedded=False):
        super().__init__(parent, "DECLARACIÓN RESPONSABLE DE CONFORMIDAD SIF", embedded=embedded)
        if not embedded:
            self.setMinimumSize(550, 450)
        self.setup_ui()

    def setup_ui(self):
        lbl_info = QLabel("<b>Certificación de Cumplimiento Legal (Ley General Tributaria):</b>")
        lbl_info.setStyleSheet("color: #FFB800; font-size: 13px; font-weight: bold;")
        self.content_layout.addWidget(lbl_info)

        self.txt_declaration = QTextBrowser()
        self.txt_declaration.setStyleSheet("background-color: #0A0F1D; color: #E2E8F0; border: 1px solid rgba(255, 184, 0, 30); font-family: 'Consolas', monospace; font-size: 11px; padding: 10px;")
        self.txt_declaration.setOpenExternalLinks(True)
        self.content_layout.addWidget(self.txt_declaration)

        # Cargar los datos desde el backend
        api = getattr(self.parent(), 'api_client', None)
        if not api and self.parent() and hasattr(self.parent(), 'thread') and hasattr(self.parent().thread, 'api'):
            api = self.parent().thread.api
        if api:
            try:
                res = api.get_compliance_declaration()
                if res.get("status") == "ok":
                    comp = res.get("compliance", {})
                    text = (
                        f"<b>DESARROLLADOR:</b> {comp.get('developer')}<br>"
                        f"<b>SISTEMA INFORMÁTICO:</b> {comp.get('software_name')} v{comp.get('version')}<br>"
                        f"<b>NORMATIVA APLICABLE:</b> {comp.get('regulation')}<br>"
                        f"<b>FECHA DE CERTIFICACIÓN:</b> {comp.get('certified_date')}<br><br>"
                        f"<hr style='border-color: rgba(255, 184, 0, 30);'><br>"
                        f"<b>DECLARACIÓN FORMAL DE CONFORMIDAD:</b><br><br>"
                        f"<i>\"{comp.get('statement')}\"</i><br><br>"
                        f"<hr style='border-color: rgba(255, 184, 0, 30);'><br>"
                        f"<font color='#10B981'><b>FIRMA DIGITAL REGLAMENTARIA:</b></font><br>"
                        f"<small>{comp.get('signature')}</small>"
                    )
                    self.txt_declaration.setHtml(text)
                else:
                    self.txt_declaration.setPlainText(f"Error al obtener declaración del backend: {res.get('message')}")
            except Exception as e:
                self.txt_declaration.setPlainText(f"Error de conexión con el backend: {e}")
        else:
            self.txt_declaration.setPlainText("API no disponible en este momento.")

        btn_close = QPushButton("Cerrar")
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet("background-color: rgba(255, 184, 0, 0.15); border-color: #FFB800; color: #FFD25F;")
        self.content_layout.addWidget(btn_close)


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

        title = QLabel("⚠️ REVISIÓN PREVIA FISCAL REGLAMENTARIA")
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
        if getattr(self, 'embedded', False):
            self.btn_close.hide()
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


class MailWidget(AlfonsoBaseDialog):
    """Interfaz gráfica nativa para el cliente de Correo Electrónico (ALFONSO MAIL)."""
    def __init__(self, api_client, parent=None, embedded=False):
        super().__init__(parent, "ALFONSO MAIL", modal=False, embedded=embedded)
        self.api = api_client
        if not embedded:
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
    def __init__(self, parent_dashboard, embedded=False):
        super().__init__(parent_dashboard, "ALFONSO CONFIGURATION", modal=False, embedded=embedded)
        self.dashboard = parent_dashboard
        if not embedded:
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
    def __init__(self, parent_dashboard, embedded=False):
        super().__init__(parent_dashboard, "ALFONSO AEAT AUTOFILL", modal=False, embedded=embedded)
        self.dashboard = parent_dashboard
        if not embedded:
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
        
        api = getattr(self.dashboard, 'api_client', None)
        if not api and hasattr(self.dashboard, 'thread') and hasattr(self.dashboard.thread, 'api'):
            api = self.dashboard.thread.api
            
        res = None
        if api:
            try:
                res = api.get_tax_aggregates(year)
            except Exception as e:
                res = {"status": "error", "message": str(e)}
        else:
            res = {"status": "error", "message": "API no disponible"}
        
        self.btn_load_data.setText("CARGAR DATOS")
        self.btn_load_data.setEnabled(True)
        
        if res and res.get("status") == "ok":
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
            # Fallback seguro: lectura directa de SQLite para evitar popups intrusivos en el inicio
            try:
                from app.adapters.memory.memory import _get_connection
                from app.utils.encryption import encryptor
                
                income_base = 0.0
                income_iva = 0.0
                expense_base = 0.0
                expense_iva = 0.0
                
                with _get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT base_imponible, iva_amount, category, date, year 
                        FROM invoices 
                        WHERE year = ?
                    """, (year,))
                    for row in cursor.fetchall():
                        try:
                            d_str = row["date"]
                            m = int(d_str[5:7]) if len(d_str) >= 7 else 1
                            q = (m - 1) // 3 + 1
                            if q != quarter:
                                continue
                            b = float(encryptor.decrypt(row["base_imponible"]))
                            v = float(encryptor.decrypt(row["iva_amount"])) if row["iva_amount"] else 0.0
                            if row["category"] == "ingreso":
                                income_base += b
                                income_iva += v
                            else:
                                expense_base += b
                                expense_iva += v
                        except Exception:
                            pass
                            
                self.income_base = income_base
                self.income_iva = income_iva
                self.expense_base = expense_base
                self.expense_iva = expense_iva
                net = income_iva - expense_iva
                
                self.lbl_income_base.setText(f"{self.income_base:,.2f} €")
                self.lbl_income_iva.setText(f"{self.income_iva:,.2f} €")
                self.lbl_expense_base.setText(f"{self.expense_base:,.2f} €")
                self.lbl_expense_iva.setText(f"{self.expense_iva:,.2f} €")
                self.lbl_result.setText(f"Resultado IVA Neto Estimado (Casilla [71]): {net:,.2f} €")
            except Exception:
                self.lbl_income_base.setText("0.00 €")
                self.lbl_income_iva.setText("0.00 €")
                self.lbl_expense_base.setText("0.00 €")
                self.lbl_expense_iva.setText("0.00 €")
                self.lbl_result.setText("Resultado IVA Neto Estimado (Casilla [71]): 0.00 €")
            
        try:
            irpf_ingresos = self.income_base
            irpf_gastos = self.expense_base
            rendimiento = max(0.0, irpf_ingresos - irpf_gastos)
            cuota_20 = rendimiento * 0.20
            self.lbl_irpf_ingresos.setText(f"{irpf_ingresos:,.2f} €")
            self.lbl_irpf_gastos.setText(f"{irpf_gastos:,.2f} €")
            self.lbl_irpf_rendimiento.setText(f"{rendimiento:,.2f} €")
            self.lbl_irpf_cuota.setText(f"{cuota_20:,.2f} €")
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
            api = getattr(self.dashboard, 'api_client', None)
            if not api and hasattr(self.dashboard, 'thread') and hasattr(self.dashboard.thread, 'api'):
                api = self.dashboard.thread.api
            if api:
                res = api.get_memory_detail(session_id)
            else:
                res = {"status": "error"}
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
    def __init__(self, parent=None, api_client=None, embedded=False):
        self.api = api_client
        super().__init__(parent, "CONCILIACIÓN BANCARIA AUTOMÁTICA Y MANUAL", embedded=embedded)
        if not embedded:
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
    def __init__(self, parent=None, embedded=False):
        super().__init__(parent, "PLAN PREMIUM Y TRANSFERENCIAS", embedded=embedded)
        if not embedded:
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
