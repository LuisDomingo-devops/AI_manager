import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

class AlfonsoContactsListPanel(QWidget):
    """Panel para gestionar el directorio de Clientes y Proveedores."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.api = main_window.api_client
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("Directorio de Contactos")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #F8FAFC;")
        header_layout.addWidget(title)

        self.cb_filter = QComboBox()
        self.cb_filter.addItems(["Todos", "Cliente", "Proveedor", "Ambos"])
        self.cb_filter.currentTextChanged.connect(self.load_data)
        self.cb_filter.setStyleSheet("""
            QComboBox { background: #1E293B; border: 1px solid #334155; padding: 6px; color: #F8FAFC; border-radius: 4px; }
        """)
        header_layout.addWidget(QLabel("Filtro:"))
        header_layout.addWidget(self.cb_filter)

        header_layout.addStretch()

        btn_new = QPushButton(" + Nuevo Contacto")
        btn_new.setStyleSheet("""
            QPushButton { background-color: #4F46E5; color: white; border-radius: 6px; padding: 8px 16px; font-weight: bold; }
            QPushButton:hover { background-color: #4338CA; }
        """)
        btn_new.clicked.connect(self.go_to_new_contact)
        header_layout.addWidget(btn_new)
        
        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self.load_data)
        header_layout.addWidget(btn_refresh)

        layout.addLayout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "NIF/CIF", "Email", "Teléfono", "Tipo", "Acciones"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0F172A; color: #F8FAFC; border: 1px solid #1E293B; border-radius: 8px; }
            QHeaderView::section { background-color: #1E293B; color: #94A3B8; font-weight: bold; padding: 8px; border: none; }
        """)
        layout.addWidget(self.table)

    def load_data(self):
        try:
            contact_type = self.cb_filter.currentText()
            endpoint = "/billing/contacts"
            if contact_type != "Todos":
                endpoint += f"?contact_type={contact_type}"
            
            response = self.api.get(endpoint)
            contacts = response.get("contacts", [])
            
            self.table.setRowCount(0)
            for i, c in enumerate(contacts):
                self.table.insertRow(i)
                self.table.setItem(i, 0, QTableWidgetItem(str(c.get("id", ""))))
                self.table.setItem(i, 1, QTableWidgetItem(str(c.get("name", "") or "")))
                self.table.setItem(i, 2, QTableWidgetItem(str(c.get("nif", "") or "")))
                self.table.setItem(i, 3, QTableWidgetItem(str(c.get("email", "") or "")))
                self.table.setItem(i, 4, QTableWidgetItem(str(c.get("phone", "") or "")))
                
                type_str = str(c.get("contact_type", "") or "")
                type_item = QTableWidgetItem(type_str)
                if type_str == "Cliente":
                    type_item.setForeground(QColor("#34D399"))
                elif c["contact_type"] == "Proveedor":
                    type_item.setForeground(QColor("#F87171"))
                self.table.setItem(i, 5, type_item)
                
                btn_del = QPushButton("Eliminar")
                btn_del.setStyleSheet("background-color: #EF4444; color: white; padding: 4px; border-radius: 4px;")
                btn_del.clicked.connect(lambda checked, cid=c["id"]: self.delete_contact(cid))
                self.table.setCellWidget(i, 6, btn_del)
                
        except Exception as e:
            print(f"[ERROR] load_data en contactos_list_panel falló: {repr(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "Error", f"No se pudo cargar el directorio: {repr(e)}")

    def delete_contact(self, contact_id):
        reply = QMessageBox.question(self, "Confirmar", "¿Seguro que deseas eliminar (soft delete) este contacto?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.api.delete(f"/billing/contacts/{contact_id}")
                self.load_data()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error al eliminar: {str(e)}")

    def go_to_new_contact(self):
        if hasattr(self.main_window, 'view_new_contact'):
            self.main_window.view_new_contact.clear_form()
            if hasattr(self.main_window, 'central_stack'):
                self.main_window.central_stack.setCurrentWidget(self.main_window.view_new_contact)
            elif hasattr(self.main_window, 'stack'):
                self.main_window.stack.setCurrentWidget(self.main_window.view_new_contact)

    def showEvent(self, event):
        super().showEvent(event)
        self.load_data()
