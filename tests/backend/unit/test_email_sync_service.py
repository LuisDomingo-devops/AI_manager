import pytest
import sqlite3
from app.domain.services.email_sync_service import EmailSyncService
from app.infrastructure.database.repositories.invoice_proposal_repository import InvoiceProposalRepository
from app.domain.schemas import EmailAccountConfigDTO
from app.adapters.memory.memory import write_transaction


@pytest.fixture(autouse=True)
def clean_test_db():
    InvoiceProposalRepository._ensure_schema()
    with write_transaction() as conn:
        conn.execute("DELETE FROM mail_account_configs")
        conn.execute("DELETE FROM invoice_approval_proposals")
        try:
            conn.execute("DELETE FROM emails")
        except sqlite3.OperationalError:
            pass
    yield


def test_inbox_disconnected_by_default():
    """Verifica que sin credenciales configuradas el estado es Desconectado."""
    service = EmailSyncService()
    status = service.get_inbox_status()
    assert status.is_connected is False
    assert "Desconectado: configure su cuenta de correo" in status.status_label
    assert status.account_email is None
    assert status.unread_emails_count == 0


def test_inbox_no_mock_emails_seeded():
    """Verifica que comprobar el estado de buzón no inyecta jamás correos simulados."""
    service = EmailSyncService()
    service.get_inbox_status()

    from app.infrastructure.database.mail_db import list_emails
    emails = list_emails()
    assert len(emails) == 0


def test_filter_valid_invoice_attachments():
    """Verifica el filtrado estricto de extensiones válidas de facturas (.pdf, .jpg, .jpeg, .png)."""
    service = EmailSyncService()
    
    assert service.is_valid_invoice_attachment("factura_luz.pdf") is True
    assert service.is_valid_invoice_attachment("TICKET_2026.JPG") is True
    assert service.is_valid_invoice_attachment("recibo.jpeg") is True
    assert service.is_valid_invoice_attachment("captura_fra.png") is True
    
    # Extensiones no válidas
    assert service.is_valid_invoice_attachment("virus.exe") is False
    assert service.is_valid_invoice_attachment("archivo.zip") is False
    assert service.is_valid_invoice_attachment("nota.txt") is False
    assert service.is_valid_invoice_attachment("presupuesto.docx") is False


def test_configure_and_retrieve_email_account():
    """Verifica que la configuración se almacena y recupera correctamente."""
    service = EmailSyncService()
    cfg = EmailAccountConfigDTO(
        imap_host="imap.gmail.com",
        imap_port=993,
        imap_user="contabilidad@autonomo.es",
        imap_password="app-password-secret-1234",
        use_ssl=True,
        mailbox_folder="INBOX"
    )
    service.configure_account(cfg)

    active_cfg = service.get_active_config()
    assert active_cfg is not None
    assert active_cfg.imap_host == "imap.gmail.com"
    assert active_cfg.imap_user == "contabilidad@autonomo.es"
    assert active_cfg.imap_password == "app-password-secret-1234"

    status = service.get_inbox_status()
    assert status.is_connected is True
    assert status.account_email == "contabilidad@autonomo.es"
