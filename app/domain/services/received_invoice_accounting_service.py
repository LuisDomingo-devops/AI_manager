from datetime import datetime
import uuid
from decimal import Decimal
from typing import Optional, List, Dict, Any

from app.domain.models.billing import InvoiceStatus
from app.domain.schemas import (
    ExtractedInvoiceMetadataDTO,
    InvoiceApprovalProposalDTO,
    ProposedJournalLineDTO,
    InvoiceProcessingStatus,
    InvoiceApprovalResultDTO,
)
from app.infrastructure.database.repositories.invoice_proposal_repository import (
    InvoiceProposalRepository,
)
from app.adapters.memory.memory import write_transaction
from app.domain.accounting.services import AccountingService
from app.domain.accounting.ports import RecordJournalEntryCommand, JournalLineDTO
from app.utils.logger import app_logger, error_logger


class ReceivedInvoiceAccountingService:
    """
    Servicio de orquestación para deduplicación, gestión de propuestas
    y contabilización de facturas de gasto recibidas en el Libro Diario PGC.
    """

    def __init__(self, accounting_service: Optional[AccountingService] = None):
        self.accounting_service = accounting_service or AccountingService()

    def check_duplicate(self, sender_nif: str, invoice_number: str) -> bool:
        """Comprueba si una factura ya fue registrada en propuestas o en la tabla oficial de facturas."""
        # 1. Comprobar en repositorio de propuestas
        existing_prop = InvoiceProposalRepository.find_by_nif_and_number(sender_nif, invoice_number)
        if existing_prop and existing_prop.status in (InvoiceProcessingStatus.PENDING_APPROVAL, InvoiceProcessingStatus.APPROVED):
            return True

        # 2. Comprobar en la tabla invoices
        try:
            with write_transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM invoices WHERE UPPER(TRIM(issuer_nif)) = ? AND UPPER(TRIM(invoice_id)) = ? LIMIT 1",
                    (sender_nif.strip().upper(), invoice_number.strip().upper())
                )
                if cursor.fetchone():
                    return True
        except Exception:
            pass

        return False

    def create_proposal_from_metadata(
        self,
        metadata: ExtractedInvoiceMetadataDTO
    ) -> InvoiceApprovalProposalDTO:
        """Crea y persiste una propuesta de aprobación verificando deduplicación."""
        is_dup = self.check_duplicate(metadata.sender_nif, metadata.invoice_number)
        status = InvoiceProcessingStatus.DUPLICATE if is_dup else InvoiceProcessingStatus.PENDING_APPROVAL
        dup_warning = "Factura ya registrada previamente con este NIF y número." if is_dup else None

        # Líneas de propuesta contable
        total_base = sum(t.tax_base for t in metadata.taxes) if metadata.taxes else metadata.total_amount
        total_tax = sum(t.tax_amount for t in metadata.taxes)

        proposed_lines = [
            ProposedJournalLineDTO(
                account_code=metadata.suggested_pgc_account,
                account_name=metadata.suggested_pgc_account_name,
                debit=total_base,
                credit=Decimal("0.00")
            )
        ]
        if total_tax > 0:
            proposed_lines.append(
                ProposedJournalLineDTO(
                    account_code="4720000",
                    account_name="Hacienda Pública, IVA soportado",
                    debit=total_tax,
                    credit=Decimal("0.00")
                )
            )
        if metadata.irpf_retention_amount > 0:
            proposed_lines.append(
                ProposedJournalLineDTO(
                    account_code="4751000",
                    account_name="HP acreedora por retenciones practicadas",
                    debit=Decimal("0.00"),
                    credit=metadata.irpf_retention_amount
                )
            )
        proposed_lines.append(
            ProposedJournalLineDTO(
                account_code="4100000",
                account_name="Acreedores por prestaciones de servicios",
                debit=Decimal("0.00"),
                credit=metadata.total_amount
            )
        )

        proposal = InvoiceApprovalProposalDTO(
            proposal_id=str(uuid.uuid4()),
            status=status,
            metadata=metadata,
            proposed_entry_lines=proposed_lines,
            created_at=metadata.issue_date,
            duplicate_warning=dup_warning
        )

        InvoiceProposalRepository.save_proposal(proposal)
        return proposal

    def approve_and_record_proposal(
        self,
        proposal_id: str,
        tenant_id: str = "default_tenant",
        confirmed_pgc_account: Optional[str] = None,
        custom_concept: Optional[str] = None,
        target_partner_account: Optional[str] = None
    ) -> InvoiceApprovalResultDTO:
        """
        Aprueba la propuesta, guarda la factura en invoices con status=RECEIVED
        y registra el asiento contable balanceado en el Libro Diario PGC.
        """
        proposal = InvoiceProposalRepository.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Propuesta {proposal_id} no encontrada")

        meta = proposal.metadata
        expense_account = confirmed_pgc_account or meta.suggested_pgc_account
        partner_account = target_partner_account or "4100000"
        concept = custom_concept or f"Fra. Recibida {meta.invoice_number} - {meta.sender_name}"

        # 1. Guardar factura en invoices con status RECEIVED
        total_base = sum(t.tax_base for t in meta.taxes) if meta.taxes else meta.total_amount
        total_tax = sum(t.tax_amount for t in meta.taxes)

        date_str = meta.issue_date or datetime.now().strftime("%Y-%m-%d")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            year_val = dt.year
            quarter_val = (dt.month - 1) // 3 + 1
        except Exception:
            year_val = datetime.now().year
            quarter_val = (datetime.now().month - 1) // 3 + 1

        primary_tax = meta.taxes[0] if meta.taxes else None
        iva_rate_val = float(primary_tax.tax_rate) if primary_tax else 21.0

        with write_transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='invoices'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(invoices)")
                cols = [row[1] for row in cursor.fetchall()]
                if "base_imponible" in cols and "date" in cols:
                    cursor.execute("""
                        INSERT INTO invoices (
                            invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                            base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount,
                            total_amount, status, quarter, year, category, concept, pdf_path
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        meta.invoice_number,
                        date_str,
                        meta.sender_name,
                        meta.sender_nif,
                        "Mi Empresa / Autónomo",
                        "B99999999",
                        float(total_base),
                        iva_rate_val,
                        float(total_tax),
                        float(meta.irpf_retention_rate),
                        float(meta.irpf_retention_amount),
                        float(meta.total_amount),
                        InvoiceStatus.RECEIVED.value,
                        quarter_val,
                        year_val,
                        "gasto",
                        f"Factura recibida {meta.invoice_number} de {meta.sender_name}",
                        meta.attached_pdf_path
                    ))

        # 2. Registrar asiento contable mediante AccountingService
        fiscal_year = int(meta.issue_date[:4]) if len(meta.issue_date) >= 4 else 2026
        journal_lines = [
            JournalLineDTO(
                account_code=expense_account,
                account_name=meta.suggested_pgc_account_name,
                debit=total_base,
                credit=Decimal("0.00"),
                concept=concept
            )
        ]
        if total_tax > 0:
            journal_lines.append(
                JournalLineDTO(
                    account_code="4720000",
                    account_name="Hacienda Pública, IVA soportado",
                    debit=total_tax,
                    credit=Decimal("0.00"),
                    concept=concept
                )
            )
        if meta.irpf_retention_amount > 0:
            journal_lines.append(
                JournalLineDTO(
                    account_code="4751000",
                    account_name="HP acreedora por retenciones practicadas",
                    debit=Decimal("0.00"),
                    credit=meta.irpf_retention_amount,
                    concept=concept
                )
            )
        journal_lines.append(
            JournalLineDTO(
                account_code=partner_account,
                account_name="Acreedores por prestaciones de servicios",
                debit=Decimal("0.00"),
                credit=meta.total_amount,
                concept=concept
            )
        )

        cmd = RecordJournalEntryCommand(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            entry_date=meta.issue_date,
            concept=concept,
            lines=journal_lines,
            source_document_ref=meta.invoice_number
        )

        entry_view = self.accounting_service.record_entry(cmd)
        entry_id = entry_view.id

        # 3. Actualizar estado de la propuesta
        InvoiceProposalRepository.update_proposal_status(
            proposal_id=proposal_id,
            status=InvoiceProcessingStatus.APPROVED,
            journal_entry_id=entry_id
        )

        return InvoiceApprovalResultDTO(
            proposal_id=proposal_id,
            invoice_id=meta.invoice_number,
            journal_entry_id=entry_id,
            status=InvoiceProcessingStatus.APPROVED,
            invoice_status=InvoiceStatus.RECEIVED.value,
            message="Factura de proveedor aprobada y contabilizada con éxito en el Libro Diario PGC.",
            is_success=True
        )

    # Alias canónico
    approve_proposal = approve_and_record_proposal

    def reject_proposal(
        self,
        proposal_id: str,
        reason: Optional[str] = None
    ) -> InvoiceApprovalResultDTO:
        """Marca una propuesta como rechazada sin generar factura ni asiento contable."""
        proposal = InvoiceProposalRepository.get_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"No existe la propuesta con id {proposal_id}")

        InvoiceProposalRepository.update_proposal_status(
            proposal_id=proposal_id,
            status=InvoiceProcessingStatus.REJECTED
        )

        return InvoiceApprovalResultDTO(
            proposal_id=proposal_id,
            invoice_id=None,
            journal_entry_id=None,
            status=InvoiceProcessingStatus.REJECTED,
            invoice_status=None,
            message=f"Propuesta rechazada. Motivo: {reason or 'Descartada por el usuario'}",
            is_success=True
        )
