import os
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from unittest.mock import MagicMock, patch
import pytest
from pathlib import Path

from app.domain.services.email_sync_service import EmailSyncService
from app.domain.schemas import EmailAccountConfigDTO
from app.adapters.memory.memory import write_transaction


@pytest.fixture(autouse=True)
def clean_test_env():
    from app.infrastructure.database.repositories.invoice_proposal_repository import InvoiceProposalRepository
    InvoiceProposalRepository._ensure_schema()
    with write_transaction() as conn:
        conn.execute("DELETE FROM mail_account_configs")
        conn.execute("DELETE FROM invoice_approval_proposals")
    yield


def create_sample_email_with_pdf(sender: str, subject: str, pdf_filename: str, pdf_bytes: bytes) -> bytes:
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = "autonomo@alfonso.dev"
    msg["Subject"] = subject
    msg["Date"] = "Mon, 15 Jun 2026 10:00:00 +0200"

    body = MIMEText("Adjuntamos su factura correspondiente al mes de mayo de 2026.", "plain", "utf-8")
    msg.attach(body)

    part = MIMEApplication(pdf_bytes, _subtype="pdf")
    part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(part)

    return msg.as_bytes()


@pytest.mark.asyncio
async def test_email_sync_integration_downloads_attachment_and_stores():
    """Valida la sincronización IMAP, extracción de adjunto PDF y guardado en disco."""
    service = EmailSyncService()
    cfg = EmailAccountConfigDTO(
        imap_host="imap.example.com",
        imap_port=993,
        imap_user="test@example.com",
        imap_password="test-password-1234",
        use_ssl=True,
        mailbox_folder="INBOX"
    )
    service.configure_account(cfg)

    # Crear correo simulado con PDF real
    pdf_content = b"%PDF-1.4 sample invoice content for testing purposes"
    raw_email = create_sample_email_with_pdf(
        sender="facturacion@telefonica.es",
        subject="Su factura de Telefónica Mayo 2026",
        pdf_filename="Factura_TE_2026_05.pdf",
        pdf_bytes=pdf_content
    )

    # Mock de imaplib.IMAP4_SSL
    mock_imap = MagicMock()
    mock_imap.login.return_value = ("OK", [b"Logged in"])
    mock_imap.select.return_value = ("OK", [b"1"])
    mock_imap.search.return_value = ("OK", [b"101"])
    mock_imap.fetch.side_effect = [
        ("OK", [(b"101", raw_email)]),
        ("OK", [(b"101", b"FLAGS (\\Seen)")])
    ]

    with patch("imaplib.IMAP4_SSL", return_value=mock_imap):
        result = await service.sync_emails()

        assert result.status == "ok"
        assert result.emails_processed == 1
        assert result.attachments_downloaded == 1

        # Verificar que el archivo se ha guardado físicamente en data/invoices_received/
        downloaded_files = list(Path("data/invoices_received").glob("**/*Factura_TE_2026_05.pdf"))
        assert len(downloaded_files) >= 1
        saved_file = downloaded_files[0]
        assert saved_file.exists()
        assert saved_file.read_bytes() == pdf_content

        # Limpieza del archivo de prueba
        try:
            saved_file.unlink()
        except OSError:
            pass
