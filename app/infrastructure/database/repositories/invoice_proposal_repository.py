import json
import sqlite3
from typing import Optional, List, Dict, Any
from app.adapters.memory.memory import write_transaction, _get_connection
from app.infrastructure.database.concurrency import retry_on_db_lock
from app.utils.encryption import encryptor
from app.utils.logger import app_logger, error_logger
from app.domain.schemas import (
    EmailAccountConfigDTO,
    InvoiceApprovalProposalDTO,
    ExtractedInvoiceMetadataDTO,
    ProposedJournalLineDTO,
    InvoiceProcessingStatus,
)


def init_invoice_proposal_schema(conn: sqlite3.Connection) -> None:
    """Inicializa las tablas para configuración de correo y propuestas de facturas."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mail_account_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            imap_host TEXT NOT NULL,
            imap_port INTEGER NOT NULL DEFAULT 993,
            imap_user TEXT NOT NULL UNIQUE,
            imap_password TEXT NOT NULL,
            use_ssl INTEGER NOT NULL DEFAULT 1,
            mailbox_folder TEXT NOT NULL DEFAULT 'INBOX',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoice_approval_proposals (
            proposal_id TEXT PRIMARY KEY,
            source_email_id TEXT NOT NULL,
            sender_nif TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            invoice_number TEXT NOT NULL,
            issue_date TEXT NOT NULL,
            total_amount TEXT NOT NULL,
            suggested_pgc_account TEXT NOT NULL,
            attached_pdf_path TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            raw_metadata_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
            journal_entry_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP
        );
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_proposals_sender_invoice 
        ON invoice_approval_proposals(sender_nif, invoice_number);
    """)


class InvoiceProposalRepository:
    """Repositorio para la persistencia de configuraciones de correo y propuestas de facturas recibidas."""

    @staticmethod
    def _ensure_schema():
        with write_transaction() as conn:
            init_invoice_proposal_schema(conn)

    @classmethod
    @retry_on_db_lock(max_retries=10, base_delay=0.05, max_delay=1.5)
    def save_mail_config(cls, config: EmailAccountConfigDTO) -> int:
        """Guarda o actualiza la configuración de cuenta IMAP con credenciales cifradas."""
        cls._ensure_schema()
        enc_user = encryptor.encrypt(config.imap_user.strip())
        enc_pass = encryptor.encrypt(config.imap_password.strip())

        with write_transaction() as conn:
            cursor = conn.cursor()
            # Desactivar configuraciones previas
            cursor.execute("UPDATE mail_account_configs SET is_active = 0")
            
            # Buscar si existe por usuario cifrado
            cursor.execute("SELECT id FROM mail_account_configs WHERE imap_user = ?", (enc_user,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE mail_account_configs
                    SET imap_host = ?, imap_port = ?, imap_password = ?, use_ssl = ?, mailbox_folder = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    config.imap_host.strip(),
                    config.imap_port,
                    enc_pass,
                    1 if config.use_ssl else 0,
                    config.mailbox_folder.strip(),
                    existing["id"],
                ))
                config_id = existing["id"]
            else:
                cursor.execute("""
                    INSERT INTO mail_account_configs (imap_host, imap_port, imap_user, imap_password, use_ssl, mailbox_folder, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (
                    config.imap_host.strip(),
                    config.imap_port,
                    enc_user,
                    enc_pass,
                    1 if config.use_ssl else 0,
                    config.mailbox_folder.strip(),
                ))
                config_id = cursor.lastrowid
            return config_id

    @classmethod
    def get_active_mail_config(cls) -> Optional[EmailAccountConfigDTO]:
        """Obtiene la configuración de correo activa desencriptando las credenciales."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM mail_account_configs WHERE is_active = 1 ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if not row:
                return None
            try:
                dec_user = encryptor.decrypt(row["imap_user"])
                dec_pass = encryptor.decrypt(row["imap_password"])
                return EmailAccountConfigDTO(
                    imap_host=row["imap_host"],
                    imap_port=row["imap_port"],
                    imap_user=dec_user,
                    imap_password=dec_pass,
                    use_ssl=bool(row["use_ssl"]),
                    mailbox_folder=row["mailbox_folder"]
                )
            except Exception as e:
                error_logger.warning("Fallo al desencriptar credenciales de correo: %s", e)
                return None

    @classmethod
    @retry_on_db_lock(max_retries=10, base_delay=0.05, max_delay=1.5)
    def save_proposal(cls, proposal: InvoiceApprovalProposalDTO) -> str:
        """Inserta o actualiza una propuesta de factura."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            raw_meta = proposal.metadata.model_dump_json()
            cursor.execute("""
                INSERT OR REPLACE INTO invoice_approval_proposals (
                    proposal_id, source_email_id, sender_nif, sender_name,
                    invoice_number, issue_date, total_amount, suggested_pgc_account,
                    attached_pdf_path, confidence_score, raw_metadata_json, status,
                    journal_entry_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                proposal.proposal_id,
                proposal.metadata.source_email_id,
                proposal.metadata.sender_nif.strip().upper(),
                proposal.metadata.sender_name.strip(),
                proposal.metadata.invoice_number.strip().upper(),
                proposal.metadata.issue_date,
                str(proposal.metadata.total_amount),
                proposal.metadata.suggested_pgc_account,
                proposal.metadata.attached_pdf_path,
                float(proposal.metadata.confidence_score),
                raw_meta,
                proposal.status.value,
                None,
                proposal.created_at
            ))
            return proposal.proposal_id

    @classmethod
    def get_proposal(cls, proposal_id: str) -> Optional[InvoiceApprovalProposalDTO]:
        """Recupera una propuesta de factura por su ID reconstruyendo el DTO."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM invoice_approval_proposals WHERE proposal_id = ?", (proposal_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return cls._row_to_proposal_dto(row)

    @classmethod
    def find_by_nif_and_number(cls, sender_nif: str, invoice_number: str) -> Optional[InvoiceApprovalProposalDTO]:
        """Busca propuestas existentes por NIF de emisor y número de factura."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM invoice_approval_proposals WHERE sender_nif = ? AND invoice_number = ? LIMIT 1",
                (sender_nif.strip().upper(), invoice_number.strip().upper())
            )
            row = cursor.fetchone()
            if not row:
                return None
            return cls._row_to_proposal_dto(row)

    @classmethod
    def get_by_id(cls, proposal_id: str) -> Optional[InvoiceApprovalProposalDTO]:
        return cls.get_proposal(proposal_id)

    @classmethod
    def list_proposals(cls, status: Optional[str] = None) -> List[InvoiceApprovalProposalDTO]:
        """Lista propuestas filtrando opcionalmente por estado."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    "SELECT * FROM invoice_approval_proposals WHERE status = ? ORDER BY created_at DESC",
                    (status,)
                )
            else:
                cursor.execute("SELECT * FROM invoice_approval_proposals ORDER BY created_at DESC")
            rows = cursor.fetchall()
            return [cls._row_to_proposal_dto(row) for row in rows]

    @classmethod
    @retry_on_db_lock(max_retries=10, base_delay=0.05, max_delay=1.5)
    def update_proposal_status(
        cls,
        proposal_id: str,
        status: InvoiceProcessingStatus,
        journal_entry_id: Optional[str] = None
    ) -> bool:
        """Actualiza el estado de la propuesta y opcionalmente enlaza el asiento contable."""
        cls._ensure_schema()
        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE invoice_approval_proposals
                SET status = ?, journal_entry_id = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE proposal_id = ?
            """, (status.value, journal_entry_id, proposal_id))
            return cursor.rowcount > 0

    @classmethod
    def _row_to_proposal_dto(cls, row: sqlite3.Row) -> InvoiceApprovalProposalDTO:
        meta_dict = json.loads(row["raw_metadata_json"])
        metadata = ExtractedInvoiceMetadataDTO(**meta_dict)
        
        # Reconstruir líneas de propuesta de asiento
        proposed_lines = [
            ProposedJournalLineDTO(
                account_code=metadata.suggested_pgc_account,
                account_name=metadata.suggested_pgc_account_name,
                debit=sum(t.tax_base for t in metadata.taxes) if metadata.taxes else metadata.total_amount,
                credit=0.0
            )
        ]
        total_tax = sum(t.tax_amount for t in metadata.taxes)
        if total_tax > 0:
            proposed_lines.append(
                ProposedJournalLineDTO(
                    account_code="4720000",
                    account_name="Hacienda Pública, IVA soportado",
                    debit=total_tax,
                    credit=0.0
                )
            )
        if metadata.irpf_retention_amount > 0:
            proposed_lines.append(
                ProposedJournalLineDTO(
                    account_code="4751000",
                    account_name="HP acreedora por retenciones practicadas",
                    debit=0.0,
                    credit=metadata.irpf_retention_amount
                )
            )
        proposed_lines.append(
            ProposedJournalLineDTO(
                account_code="4100000",
                account_name="Acreedores por prestaciones de servicios",
                debit=0.0,
                credit=metadata.total_amount
            )
        )

        return InvoiceApprovalProposalDTO(
            proposal_id=row["proposal_id"],
            status=InvoiceProcessingStatus(row["status"]),
            metadata=metadata,
            proposed_entry_lines=proposed_lines,
            created_at=row["created_at"],
            duplicate_warning="Factura ya registrada previamente con este NIF y número." if row["status"] == "DUPLICATE" else None,
            journal_entry_id=row["journal_entry_id"] if "journal_entry_id" in row.keys() else None
        )
