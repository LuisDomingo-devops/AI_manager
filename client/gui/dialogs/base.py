import sys
import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget, QLabel, 
    QFrame, QPushButton, QTextBrowser, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont


class AlfonsoBaseDialog(QDialog):
    """
    Clase base para todos los diálogos y vistas embebidas de Alfonso.
    Asegura consistencia visual (estilo cyber/contable moderno) y facilita cambios globales de apariencia.
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
        outer_frame_style = """
            #OuterFrame {
                background-color: transparent;
                border: none;
            }
        """ if getattr(self, 'embedded', False) else """
            #OuterFrame {
                background-color: #0F172A;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """
        
        self.setStyleSheet(f"""
            QDialog {{
                background: transparent;
            }}
            QToolTip {{
                background-color: #0F172A;
                color: #F8FAFC;
                border: 1px solid rgba(0, 240, 255, 0.5);
                border-radius: 6px;
                padding: 6px 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }}
            QScrollBar:vertical {{
                border: none;
                background: rgba(15, 23, 42, 0.3);
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: rgba(99, 102, 241, 0.4);
                min-height: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: rgba(0, 240, 255, 0.7);
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
                background: none;
            }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
                background: none;
            }}
            QScrollBar:horizontal {{
                border: none;
                background: rgba(15, 23, 42, 0.3);
                height: 8px;
                margin: 0px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal {{
                background: rgba(99, 102, 241, 0.4);
                min-width: 20px;
                border-radius: 4px;
            }}
            QScrollBar::handle:horizontal:hover {{
                background: rgba(0, 240, 255, 0.7);
            }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
                width: 0px;
                border: none;
                background: none;
            }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
                background: none;
            }}
            {outer_frame_style}
            #TitleBar {{
                background-color: rgba(99, 102, 241, 0.05);
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }}
            #TitleLabel {{
                font-family: 'Segoe UI', 'Inter', sans-serif;
            }}
            QLabel {{
                color: #CBD5E1;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
            }}
            QLineEdit, QComboBox, QTextEdit, QListWidget {{
                background-color: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(99, 102, 241, 0.3);
                border-radius: 8px;
                color: #F8FAFC;
                padding: 6px;
                font-family: 'Segoe UI', sans-serif;
            }}
            QComboBox QAbstractItemView {{
                background-color: #1E293B;
                border: 1px solid #6366F1;
                color: #F8FAFC;
                selection-background-color: #6366F1;
                selection-color: #FFFFFF;
            }}
            QMenu {{
                background-color: #1E293B;
                border: 1px solid rgba(255, 255, 255, 0.1);
                color: #F8FAFC;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 6px 20px;
                color: #CBD5E1;
            }}
            QMenu::item:selected {{
                background-color: #6366F1;
                color: #FFFFFF;
            }}
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QListWidget:focus {{
                border: 1px solid #00F0FF;
            }}
            QTableWidget, QTableView {{
                background-color: #0B111E;
                alternate-background-color: #0F172A;
                gridline-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                color: #E2E8F0;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
                selection-background-color: rgba(0, 240, 255, 0.18);
                selection-color: #00F0FF;
                outline: none;
            }}
            QTableWidget::item, QTableView::item {{
                padding: 6px 10px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            }}
            QTableWidget::item:hover, QTableView::item:hover {{
                background-color: rgba(99, 102, 241, 0.12);
                color: #FFFFFF;
            }}
            QTableWidget::item:selected, QTableView::item:selected {{
                background-color: rgba(0, 240, 255, 0.2);
                color: #00F0FF;
                font-weight: bold;
            }}
            QHeaderView {{
                background-color: transparent;
                border: none;
            }}
            QHeaderView::section {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1E293B, stop:1 #0F172A);
                color: #00F0FF;
                font-weight: bold;
                font-size: 10px;
                letter-spacing: 0.8px;
                padding: 8px 10px;
                border: none;
                border-bottom: 2px solid rgba(0, 240, 255, 0.4);
                border-right: 1px solid rgba(255, 255, 255, 0.05);
                font-family: 'Segoe UI', sans-serif;
            }}
            QHeaderView::section:hover {{
                background: #334155;
                color: #FFFFFF;
            }}
            QTableCornerButton::section {{
                background-color: #0F172A;
                border: none;
                border-bottom: 2px solid rgba(0, 240, 255, 0.4);
            }}
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollArea QWidget {{
                background-color: transparent;
            }}
            QPushButton {{
                background-color: rgba(255, 255, 255, 0.05);
                border: 1px solid rgba(255, 255, 255, 0.15);
                color: #CBD5E1;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 8px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: rgba(99, 102, 241, 0.15);
                color: #FFFFFF;
                border-color: rgba(99, 102, 241, 0.4);
            }}
            QPushButton:pressed {{
                background-color: #6366F1;
                color: #FFFFFF;
            }}
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
