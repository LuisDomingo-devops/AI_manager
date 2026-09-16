from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QLabel, QMessageBox, QHBoxLayout, QComboBox
)
from PyQt6.QtCore import Qt

from client.gui.panels.base_panel import AlfonsoBasePanel

class AlfonsoContactFormPanel(AlfonsoBasePanel):
    """Formulario para crear un nuevo contacto (Cliente/Proveedor)."""

    def __init__(self, main_window):
        super().__init__(None, title="Alta de Nuevo Contacto", subtitle="Introduce los datos del nuevo cliente o proveedor.")
        self.main_window = main_window
        self.api = main_window.api_client
        self.setup_ui()

    def setup_ui(self):


        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.txt_name = QLineEdit()
        self.txt_nif = QLineEdit()
        self.txt_email = QLineEdit()
        self.txt_phone = QLineEdit()
        self.txt_address = QLineEdit()
        self.txt_iban = QLineEdit()
        
        self.cb_type = QComboBox()
        self.cb_type.addItems(["Cliente", "Proveedor", "Ambos"])

        form_layout.addRow(QLabel("Nombre/Razón Social:"), self.txt_name)
        form_layout.addRow(QLabel("NIF/CIF:"), self.txt_nif)
        form_layout.addRow(QLabel("Email:"), self.txt_email)
        form_layout.addRow(QLabel("Teléfono:"), self.txt_phone)
        form_layout.addRow(QLabel("Dirección:"), self.txt_address)
        form_layout.addRow(QLabel("IBAN bancario:"), self.txt_iban)
        form_layout.addRow(QLabel("Tipo de Contacto:"), self.cb_type)

        self.add_layout(form_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch() # Empuja los botones a la derecha y evita que ocupen todo el ancho
        
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.cancel)
        
        btn_save = QPushButton("Guardar Contacto")
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self.save_contact)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_save)
        self.add_layout(btn_layout)
        self.content_layout.addStretch()

    def clear_form(self):
        self.txt_name.clear()
        self.txt_nif.clear()
        self.txt_email.clear()
        self.txt_phone.clear()
        self.txt_address.clear()
        self.txt_iban.clear()
        self.cb_type.setCurrentIndex(0)

    def save_contact(self):
        name = self.txt_name.text().strip()
        nif = self.txt_nif.text().strip()
        if not name or not nif:
            QMessageBox.warning(self, "Validación", "Nombre y NIF son obligatorios.")
            return

        payload = {
            "name": name,
            "nif": nif,
            "email": self.txt_email.text().strip(),
            "phone": self.txt_phone.text().strip(),
            "address": self.txt_address.text().strip(),
            "iban": self.txt_iban.text().strip(),
            "contact_type": self.cb_type.currentText()
        }

        try:
            res = self.api.post("/billing/contacts", payload)
            if res.get("status") == "ok":
                QMessageBox.information(self, "Éxito", "Contacto guardado correctamente.")
                self.clear_form()
                if hasattr(self.main_window, 'view_contacts_list'):
                    self.main_window.stack.setCurrentWidget(self.main_window.view_contacts_list)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al guardar contacto: {str(e)}")

    def cancel(self):
        if hasattr(self.main_window, 'view_contacts_list'):
            self.main_window.stack.setCurrentWidget(self.main_window.view_contacts_list)
