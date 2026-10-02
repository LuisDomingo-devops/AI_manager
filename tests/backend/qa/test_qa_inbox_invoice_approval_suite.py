import os
import sys
from decimal import Decimal
import pytest
from PyQt6.QtWidgets import QApplication

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
    init_invoice_proposal_schema,
)
from client.gui.dialogs.pending_invoice_card_widget import PendingInvoiceCardWidget


@pytest.fixture(scope="session")
def qapp():
    """Garantiza la instancia global de QApplication para los tests de interfaz PyQt6."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app


@pytest.fixture(autouse=True)
def setup_test_db(clean_db_conn):
    """Inicializa el esquema de base de datos para propuestas."""
    init_invoice_proposal_schema(clean_db_conn)
    yield


def test_qa_pending_invoice_card_display_and_confidence_badge(qapp):
    """
    QA Test: La tarjeta muestra correctamente los datos de la factura,
    el badge de confianza >= 0.85 en color verde y la cuenta PGC sugerida.
    """
    metadata = ExtractedInvoiceMetadataDTO(
        sender_nif="A28015865",
        sender_name="TELEFONICA DE ESPAÑA S.A.U.",
        invoice_number="TE-2026-0042",
        issue_date="2026-06-01",
        taxes=[
            InvoiceTaxBreakdownDTO(
                tax_rate=Decimal("21.00"),
                tax_base=Decimal("80.00"),
                tax_amount=Decimal("16.80"),
            )
        ],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("96.80"),
        suggested_pgc_account="6280001",
        suggested_pgc_account_name="Suministros - Comunicaciones",
        source_email_id="msg_qa_01",
        attached_pdf_path="data/invoices_received/2026/06/te.pdf",
        confidence_score=0.92,
    )

    service = ReceivedInvoiceAccountingService()
    proposal = service.create_proposal_from_metadata(metadata)

    card = PendingInvoiceCardWidget(proposal=proposal, accounting_service=service)

    # Verificación de labels visuales
    assert "TELEFONICA DE ESPAÑA S.A.U." in card.lbl_sender.text()
    assert "TE-2026-0042" in card.lbl_invoice.text()
    assert "96.80" in card.lbl_total.text()
    assert "92%" in card.lbl_confidence.text()
    assert card.is_high_confidence is True
    assert card.txt_account.text() == "6280001"


def test_qa_pending_invoice_card_approve_action(qapp):
    """
    QA Test: El usuario edita la cuenta contable en la tarjeta y pulsa Aprobar.
    La propuesta pasa a APPROVED, se registra en el Diario y la tarjeta emite la señal de éxito.
    """
    metadata = ExtractedInvoiceMetadataDTO(
        sender_nif="B84019283",
        sender_name="SUMINISTROS ELECTRICOS S.L.",
        invoice_number="ELE-2026-101",
        issue_date="2026-06-02",
        taxes=[
            InvoiceTaxBreakdownDTO(
                tax_rate=Decimal("21.00"),
                tax_base=Decimal("200.00"),
                tax_amount=Decimal("42.00"),
            )
        ],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("242.00"),
        suggested_pgc_account="6280002",
        suggested_pgc_account_name="Suministros - Electricidad",
        source_email_id="msg_qa_02",
        attached_pdf_path="data/invoices_received/2026/06/ele.pdf",
        confidence_score=0.88,
    )

    service = ReceivedInvoiceAccountingService()
    proposal = service.create_proposal_from_metadata(metadata)

    card = PendingInvoiceCardWidget(proposal=proposal, accounting_service=service)

    # Modificar cuenta contable en el campo de texto interactivo
    card.txt_account.setText("6280009")

    approved_signals = []
    card.proposal_approved.connect(lambda pid: approved_signals.append(pid))

    # Simular clic en el botón de aprobación
    card.btn_approve.click()

    assert len(approved_signals) == 1
    assert approved_signals[0] == proposal.proposal_id

    # Comprobar en base de datos
    updated_prop = InvoiceProposalRepository.get_by_id(proposal.proposal_id)
    assert updated_prop.status == InvoiceProcessingStatus.APPROVED


def test_qa_pending_invoice_card_reject_action(qapp):
    """
    QA Test: El usuario pulsa Rechazar en la tarjeta.
    La propuesta pasa a REJECTED y emite señal.
    """
    metadata = ExtractedInvoiceMetadataDTO(
        sender_nif="B99887766",
        sender_name="DESCONOCIDO PROVEEDOR",
        invoice_number="INV-DOUBT-01",
        issue_date="2026-06-03",
        taxes=[],
        irpf_retention_rate=Decimal("0.00"),
        irpf_retention_amount=Decimal("0.00"),
        total_amount=Decimal("15.00"),
        suggested_pgc_account="6290000",
        suggested_pgc_account_name="Otros servicios",
        source_email_id="msg_qa_03",
        attached_pdf_path="data/invoices_received/2026/06/doubt.pdf",
        confidence_score=0.45,
    )

    service = ReceivedInvoiceAccountingService()
    proposal = service.create_proposal_from_metadata(metadata)

    card = PendingInvoiceCardWidget(proposal=proposal, accounting_service=service)
    assert card.is_high_confidence is False

    rejected_signals = []
    card.proposal_rejected.connect(lambda pid: rejected_signals.append(pid))

    # Simular clic en el botón de rechazo
    card.btn_reject.click()

    assert len(rejected_signals) == 1
    assert rejected_signals[0] == proposal.proposal_id

    updated_prop = InvoiceProposalRepository.get_by_id(proposal.proposal_id)
    assert updated_prop.status == InvoiceProcessingStatus.REJECTED
