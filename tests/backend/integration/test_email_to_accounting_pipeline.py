import os
from decimal import Decimal
import pytest

from app.domain.models.billing import InvoiceStatus
from app.domain.schemas import (
    ExtractedInvoiceMetadataDTO,
    InvoiceTaxBreakdownDTO,
    InvoiceProcessingStatus,
)
from app.domain.services.received_invoice_accounting_service import (
    ReceivedInvoiceAccountingService,
)
from app.infrastructure.database.repositories.invoice_proposal_repository import (
    InvoiceProposalRepository,
)
from app.adapters.memory.memory import write_transaction


@pytest.fixture(autouse=True)
def setup_test_db(clean_db_conn):
    """Garantiza tablas listas antes de cada test."""
    from app.infrastructure.database.repositories.invoice_proposal_repository import init_invoice_proposal_schema
    init_invoice_proposal_schema(clean_db_conn)
    yield


def test_full_pipeline_create_proposal_and_approve_to_journal():
    """
    Test de integración E2E:
    Creación de propuesta a partir de metadatos OCR,
    edición de cuenta PGC,
    aprobación y contabilización atómica en el Libro Diario PGC.
    """
    service = ReceivedInvoiceAccountingService()

    # 1. Metadatos extraídos de factura (Telefónica)
    metadata = ExtractedInvoiceMetadataDTO(
        sender_nif="A28015865",
        sender_name="TELEFONICA DE ESPAÑA S.A.U.",
        invoice_number="TE-2026-9912",
        issue_date="2026-05-15",
        taxes=[
            InvoiceTaxBreakdownDTO(
                tax_rate=Decimal("21.00"),
                tax_base=Decimal("100.00"),
                tax_amount=Decimal("21.00"),
            )
        ],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("121.00"),
        suggested_pgc_account="6280001",
        suggested_pgc_account_name="Suministros - Comunicaciones",
        source_email_id="msg_e2e_01",
        attached_pdf_path="data/invoices_received/2026/05/telefonica.pdf",
        confidence_score=0.95,
    )

    # 2. Generar propuesta en estado pendiente
    proposal = service.create_proposal_from_metadata(metadata)
    assert proposal.status == InvoiceProcessingStatus.PENDING_APPROVAL
    assert proposal.metadata.invoice_number == "TE-2026-9912"
    assert len(proposal.proposed_entry_lines) == 3

    # Comprobar balance en las líneas propuestas iniciales
    total_debe = sum(l.debit for l in proposal.proposed_entry_lines)
    total_haber = sum(l.credit for l in proposal.proposed_entry_lines)
    assert total_debe == total_haber == Decimal("121.00")

    # 3. Aprobación con confirmación y sobreescritura de cuenta contable
    approval_result = service.approve_proposal(
        proposal_id=proposal.proposal_id,
        confirmed_pgc_account="6280005",  # Cuenta afinada por el usuario
        custom_concept="Gasto fibra óptica oficina Mayo 2026"
    )

    assert approval_result.is_success is True
    assert approval_result.journal_entry_id is not None
    assert approval_result.status == InvoiceProcessingStatus.APPROVED

    # 4. Verificar persistencia de propuesta actualizada
    updated_prop = InvoiceProposalRepository.get_by_id(proposal.proposal_id)
    assert updated_prop is not None
    assert updated_prop.status == InvoiceProcessingStatus.APPROVED
    assert updated_prop.journal_entry_id == approval_result.journal_entry_id

    # 5. Verificar inserción en tabla invoices con status RECEIVED
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT invoice_id, issuer_nif, total_amount, status FROM invoices WHERE invoice_id = ?",
            ("TE-2026-9912",)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "TE-2026-9912"
        assert row[1] == "A28015865"
        assert Decimal(str(row[2])) == Decimal("121.00")
        assert row[3] == InvoiceStatus.RECEIVED.value

    # 6. Verificar que la deduplicación ahora la detecta como duplicada
    assert service.check_duplicate("A28015865", "TE-2026-9912") is True


def test_pipeline_reject_proposal():
    """
    Test de rechazo de propuesta:
    El usuario rechaza una factura extraída errónea o spam.
    No debe registrarse asiento contable ni factura oficial.
    """
    service = ReceivedInvoiceAccountingService()

    metadata = ExtractedInvoiceMetadataDTO(
        sender_nif="B11223344",
        sender_name="SPAM PUBLICIDAD S.L.",
        invoice_number="SPAM-001",
        issue_date="2026-05-16",
        taxes=[
            InvoiceTaxBreakdownDTO(
                tax_rate=Decimal("21.00"),
                tax_base=Decimal("50.00"),
                tax_amount=Decimal("10.50"),
            )
        ],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("60.50"),
        suggested_pgc_account="6270000",
        suggested_pgc_account_name="Publicidad y propaganda",
        source_email_id="msg_e2e_spam",
        attached_pdf_path="data/invoices_received/2026/05/spam.pdf",
        confidence_score=0.40,
    )

    proposal = service.create_proposal_from_metadata(metadata)
    assert proposal.status == InvoiceProcessingStatus.PENDING_APPROVAL

    # Rechazar propuesta con motivo
    rejection = service.reject_proposal(proposal.proposal_id, reason="Correo publicitario sin valor contable")
    assert rejection.status == InvoiceProcessingStatus.REJECTED

    # Verificar que no hay factura en invoices
    with write_transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM invoices WHERE invoice_id = ?", ("SPAM-001",))
        assert cursor.fetchone() is None
