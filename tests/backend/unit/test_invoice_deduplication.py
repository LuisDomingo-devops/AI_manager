from decimal import Decimal
import pytest
from app.domain.schemas import ExtractedInvoiceMetadataDTO, InvoiceTaxBreakdownDTO, InvoiceProcessingStatus
from app.domain.services.received_invoice_accounting_service import ReceivedInvoiceAccountingService
from app.infrastructure.database.repositories.invoice_proposal_repository import InvoiceProposalRepository
from app.adapters.memory.memory import write_transaction


@pytest.fixture(autouse=True)
def clean_proposals_db():
    InvoiceProposalRepository._ensure_schema()
    with write_transaction() as conn:
        conn.execute("DELETE FROM invoice_approval_proposals")
    yield


def test_invoice_deduplication_by_nif_and_number():
    """Valida la detección de facturas duplicadas por clave compuesta (sender_nif, invoice_number)."""
    service = ReceivedInvoiceAccountingService()

    meta1 = ExtractedInvoiceMetadataDTO(
        sender_nif="B87654321",
        sender_name="Telefónica España",
        invoice_number="TE-2026/001",
        issue_date="2026-05-01",
        taxes=[InvoiceTaxBreakdownDTO(tax_rate=Decimal("21.00"), tax_base=Decimal("100.00"), tax_amount=Decimal("21.00"))],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("121.00"),
        suggested_pgc_account="6280001",
        source_email_id="email_101",
        attached_pdf_path="data/invoices_received/te_001.pdf",
        confidence_score=0.95
    )

    # 1. Primera factura: se crea normalmente como PENDING_APPROVAL
    prop1 = service.create_proposal_from_metadata(meta1)
    assert prop1.status == InvoiceProcessingStatus.PENDING_APPROVAL
    assert prop1.duplicate_warning is None

    # 2. Segunda factura idéntica: se marca como DUPLICATE
    prop2 = service.create_proposal_from_metadata(meta1)
    assert prop2.status == InvoiceProcessingStatus.DUPLICATE
    assert prop2.duplicate_warning is not None
    assert "Factura ya registrada previamente" in prop2.duplicate_warning

    # 3. Factura distinta del mismo emisor: debe aceptarse normalmente
    meta2 = meta1.model_copy(update={"invoice_number": "TE-2026/002"})
    prop3 = service.create_proposal_from_metadata(meta2)
    assert prop3.status == InvoiceProcessingStatus.PENDING_APPROVAL
