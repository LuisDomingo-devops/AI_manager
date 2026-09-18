import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from client.gui.panels.base_panel import AlfonsoBasePanel

class AlfonsoContactsListPanel(AlfonsoBasePanel):
    """Panel para gestionar el directorio de Clientes y Proveedores."""

    def __init__(self, main_window):
        super().__init__(None, title="Directorio de Contactos", subtitle="Gestiona tus clientes y proveedores.")
        self.main_window = main_window
        self.api = main_window.api_client
        self.setup_ui()

    def setup_ui(self):
        # Action bar
        header_layout = QHBoxLayout()
        header_layout.addStretch()

        self.cb_filter = QComboBox()
        self.cb_filter.addItems(["Todos", "Cliente", "Proveedor", "Ambos"])
        self.cb_filter.currentTextChanged.connect(self.load_data)
        
        header_layout.addWidget(QLabel("Filtro:"))
        header_layout.addWidget(self.cb_filter)

        btn_new = QPushButton(" + Nuevo Contacto")
        btn_new.setProperty("class", "PrimaryButton")
        btn_new.clicked.connect(self.go_to_new_contact)
        header_layout.addWidget(btn_new)
        
        btn_refresh = QPushButton("🔄 Actualizar")
        btn_refresh.clicked.connect(self.load_data)
        header_layout.addWidget(btn_refresh)

        self.add_layout(header_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Nombre", "NIF/CIF", "Email", "Teléfono", "Tipo", "Acciones"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.add_widget(self.table, stretch=1)

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
            pass
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
