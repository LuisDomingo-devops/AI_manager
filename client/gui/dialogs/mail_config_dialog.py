from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
    QLabel,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from app.domain.schemas import EmailAccountConfigDTO
from app.domain.services.email_sync_service import EmailSyncService


class MailConfigDialog(QDialog):
    """Diálogo nativo para configurar de forma segura la cuenta de correo IMAP/TLS."""

    def __init__(self, parent=None, api_client=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Cuenta de Correo (IMAP/TLS)")
        self.resize(460, 320)
        self.api_client = api_client
        self.email_service = EmailSyncService()

        self._init_ui()
        self._load_current_config()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header_lbl = QLabel("Conexión de Correo Profesional")
        header_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E293B;")
        layout.addWidget(header_lbl)

        desc_lbl = QLabel(
            "Configure su servidor IMAP sobre SSL/TLS. Para cuentas Gmail o Microsoft 365, "
            "se recomienda utilizar una contraseña de aplicación (App Password) generada en su panel de seguridad."
        )
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        layout.addWidget(desc_lbl)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("ej. imap.gmail.com o outlook.office365.com")
        form_layout.addRow("Servidor IMAP:", self.txt_host)

        self.spin_port = QSpinBox()
        self.spin_port.setRange(1, 65535)
        self.spin_port.setValue(993)
        form_layout.addRow("Puerto:", self.spin_port)

        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("ej. contabilidad@miempresa.es")
        form_layout.addRow("Usuario / Email:", self.txt_user)

        self.txt_pass = QLineEdit()
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_pass.setPlaceholderText("Contraseña o Contraseña de Aplicación")
        form_layout.addRow("Contraseña:", self.txt_pass)

        self.chk_ssl = QCheckBox("Utilizar conexión segura SSL/TLS")
        self.chk_ssl.setChecked(True)
        form_layout.addRow("", self.chk_ssl)

        layout.addLayout(form_layout)

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        buttons_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Guardar Configuración")
        self.btn_save.setStyleSheet("background-color: #6366F1; color: white; font-weight: bold; padding: 6px 14px;")
        self.btn_save.clicked.connect(self._on_save)
        buttons_layout.addWidget(self.btn_save)

        layout.addLayout(buttons_layout)

    def _load_current_config(self):
        current = self.email_service.get_active_config()
        if current:
            self.txt_host.setText(current.imap_host)
            self.spin_port.setValue(current.imap_port)
            self.txt_user.setText(current.imap_user)
            self.txt_pass.setText(current.imap_password)
            self.chk_ssl.setChecked(current.use_ssl)

    def _on_save(self):
        host = self.txt_host.text().strip()
        port = self.spin_port.value()
        user = self.txt_user.text().strip()
        password = self.txt_pass.text().strip()

        if not host or not user or not password:
            QMessageBox.warning(self, "Campos Incompletos", "Por favor, complete todos los campos de conexión.")
            return

        cfg = EmailAccountConfigDTO(
            imap_host=host,
            imap_port=port,
            imap_user=user,
            imap_password=password,
            use_ssl=self.chk_ssl.isChecked(),
            mailbox_folder="INBOX"
        )

        try:
            self.email_service.configure_account(cfg)
            QMessageBox.information(
                self,
                "Configuración Guardada",
                "Las credenciales se han cifrado y guardado con éxito."
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error al Guardar", f"No se pudo guardar la configuración: {e}")
