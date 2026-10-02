import os
import email
import imaplib
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from email.header import decode_header

from app.domain.schemas import (
    EmailAccountConfigDTO,
    InboxStatusDTO,
    EmailSyncResultDTO,
)
from app.infrastructure.database.repositories.invoice_proposal_repository import (
    InvoiceProposalRepository,
)
from app.utils.logger import app_logger, error_logger


class EmailSyncService:
    """
    Servicio de sincronización desatendida de bandejas de entrada mediante IMAP/TLS.
    Descarga adjuntos de facturas (.pdf, .jpg, .jpeg, .png) en local y evita datos falsos.
    """

    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

    def __init__(self, storage_dir: str = "data/invoices_received"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def is_valid_invoice_attachment(self, filename: str) -> bool:
        """Determina si un archivo adjunto corresponde a un formato de factura admisible."""
        if not filename:
            return False
        ext = Path(filename).suffix.lower()
        return ext in self.ALLOWED_EXTENSIONS

    def configure_account(self, config: EmailAccountConfigDTO) -> int:
        """Guarda o actualiza las credenciales de correo de forma cifrada."""
        return InvoiceProposalRepository.save_mail_config(config)

    def get_active_config(self) -> Optional[EmailAccountConfigDTO]:
        """Obtiene la configuración activa de correo desencriptada."""
        return InvoiceProposalRepository.get_active_mail_config()

    def get_inbox_status(self) -> InboxStatusDTO:
        """
        Retorna el estado de la conexión del buzón.
        Si no hay credenciales, devuelve 'Desconectado: configure su cuenta de correo'.
        """
        config = self.get_active_config()
        if not config:
            return InboxStatusDTO(
                is_connected=False,
                status_label="Desconectado: configure su cuenta de correo",
                account_email=None,
                unread_emails_count=0,
                pending_proposals_count=len(InvoiceProposalRepository.list_proposals(status="PENDING_APPROVAL")),
                last_sync_at=None
            )

        return InboxStatusDTO(
            is_connected=True,
            status_label="Conectado",
            account_email=config.imap_user,
            unread_emails_count=0,
            pending_proposals_count=len(InvoiceProposalRepository.list_proposals(status="PENDING_APPROVAL")),
            last_sync_at=None
        )

    async def sync_emails(self) -> EmailSyncResultDTO:
        """
        Ejecuta la sincronización de correos no leídos buscando facturas adjuntas.
        """
        config = self.get_active_config()
        if not config:
            return EmailSyncResultDTO(
                status="error",
                emails_processed=0,
                attachments_downloaded=0,
                invoices_extracted=0,
                proposals_created=0,
                duplicates_detected=0,
                error_message="Buzón no configurado: configure su cuenta de correo"
            )

        return self._sync_imap_blocking(config)

    def _clean_header_str(self, header_value: Any) -> str:
        if not header_value:
            return ""
        decoded = decode_header(header_value)
        parts = []
        for val, charset in decoded:
            if isinstance(val, bytes):
                if charset:
                    try:
                        parts.append(val.decode(charset, errors="ignore"))
                    except Exception:
                        parts.append(val.decode("utf-8", errors="ignore"))
                else:
                    parts.append(val.decode("utf-8", errors="ignore"))
            else:
                parts.append(str(val))
        return "".join(parts)

    def _sync_imap_blocking(self, config: EmailAccountConfigDTO) -> EmailSyncResultDTO:
        emails_processed = 0
        attachments_downloaded = 0
        invoices_extracted = 0
        proposals_created = 0
        duplicates_detected = 0

        mail = None
        try:
            if config.use_ssl:
                mail = imaplib.IMAP4_SSL(config.imap_host, config.imap_port)
            else:
                mail = imaplib.IMAP4(config.imap_host, config.imap_port)

            mail.login(config.imap_user, config.imap_password)
            mail.select(config.mailbox_folder)

            status, search_data = mail.search(None, "UNSEEN")
            if status != "OK" or not search_data or not search_data[0]:
                return EmailSyncResultDTO(
                    status="ok",
                    emails_processed=0,
                    attachments_downloaded=0,
                    invoices_extracted=0,
                    proposals_created=0,
                    duplicates_detected=0
                )

            email_ids = search_data[0].split()

            now = datetime.now()
            target_dir = self.storage_dir / str(now.year) / f"{now.month:02d}"
            target_dir.mkdir(parents=True, exist_ok=True)

            for e_id in email_ids:
                status, data = mail.fetch(e_id, "(RFC822)")
                if status != "OK" or not data:
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)
                emails_processed += 1

                for part in msg.walk():
                    content_disposition = str(part.get("Content-Disposition", ""))
                    filename = part.get_filename()

                    if filename:
                        filename = self._clean_header_str(filename)

                    if ("attachment" in content_disposition or filename) and self.is_valid_invoice_attachment(filename):
                        payload = part.get_payload(decode=True)
                        if payload:
                            unique_prefix = uuid.uuid4().hex[:8]
                            clean_filename = f"{unique_prefix}_{Path(filename).name}"
                            save_path = target_dir / clean_filename
                            save_path.write_bytes(payload)
                            attachments_downloaded += 1

                # Marcar como visto
                mail.fetch(e_id, "+FLAGS (\\Seen)")

            return EmailSyncResultDTO(
                status="ok",
                emails_processed=emails_processed,
                attachments_downloaded=attachments_downloaded,
                invoices_extracted=invoices_extracted,
                proposals_created=proposals_created,
                duplicates_detected=duplicates_detected
            )

        except Exception as e:
            error_logger.exception("Error al sincronizar buzón IMAP: %s", e)
            return EmailSyncResultDTO(
                status="error",
                emails_processed=emails_processed,
                attachments_downloaded=attachments_downloaded,
                invoices_extracted=invoices_extracted,
                proposals_created=proposals_created,
                duplicates_detected=duplicates_detected,
                error_message=str(e)
            )
        finally:
            if mail:
                try:
                    mail.close()
                except Exception:
                    pass
                try:
                    mail.logout()
                except Exception:
                    pass
