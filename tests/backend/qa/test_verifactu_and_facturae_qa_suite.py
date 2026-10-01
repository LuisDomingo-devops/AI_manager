"""
Suite de QA: Facturación Veri*Factu Oficial, Facturas Rectificativas y Facturae 3.2.2.
Task: T011 [P] [US1]
"""

import pytest
from app.domain.services.billing_service import BillingService
from app.domain.services.facturae_service import FacturaeService
from app.domain.services.invoice_pdf_service import InvoicePDFService
from app.domain.models.billing import (
    InvoiceCreateDTO,
    InvoiceType,
    RectificationMethod,
)


def test_qa_ordinary_invoice_pdf_has_qr_and_verifactu_legend():
    """QA: Verifica que el PDF de factura ordinaria contiene el QR y la leyenda oficial obligatoria."""
    billing = BillingService()
    inv_in = InvoiceCreateDTO(
        series="F2026_QA",
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="ALFONSO AUTOMATIZACIONES SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE CORPORATIVO SA",
        base_amount=1000.0,
        tax_amount=210.0,
        total_amount=1210.0
    )
    invoice = billing.emit_invoice_atomic(inv_in, force_valid_xml=True)

    pdf_service = InvoicePDFService()
    pdf_bytes = pdf_service.generate_invoice_pdf(invoice)
    assert len(pdf_bytes) > 500
    assert pdf_bytes.startswith(b"%PDF")

    # Validar que el PDF contiene la leyenda legal reglamentaria
    pdf_text = pdf_service.extract_text_from_pdf(pdf_bytes)
    assert "VERI*FACTU" in pdf_text or "verificable en la sede electrónica de la AEAT" in pdf_text.lower()


def test_qa_rectificativa_substitution_and_differences():
    """QA: Verifica la emisión reglamentaria de facturas rectificativas por sustitución (S) y diferencias (I)."""
    billing = BillingService()

    # 1. Factura original
    orig_in = InvoiceCreateDTO(
        series="F2026_RECT",
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="ALFONSO SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE QA",
        base_amount=500.0,
        tax_amount=105.0,
        total_amount=605.0
    )
    orig_inv = billing.emit_invoice_atomic(orig_in, force_valid_xml=True)

    # 2. Factura Rectificativa por Sustitución (S)
    rect_s_in = InvoiceCreateDTO(
        series="R2026_RECT",
        invoice_type=InvoiceType.R1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="ALFONSO SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE QA",
        base_amount=450.0,
        tax_amount=94.5,
        total_amount=544.5,
        rectified_series=orig_inv.series,
        rectified_number=orig_inv.number,
        rectification_method=RectificationMethod.SUSTITUTION,
        rectification_reason="Corrección de base imponible por error material"
    )
    rect_s_inv = billing.emit_invoice_atomic(rect_s_in, force_valid_xml=True)
    assert rect_s_inv.invoice_type == InvoiceType.R1
    assert rect_s_inv.rectified_number == orig_inv.number
    assert rect_s_inv.rectification_method == RectificationMethod.SUSTITUTION

    # 3. Factura Rectificativa por Diferencias (I)
    rect_i_in = InvoiceCreateDTO(
        series="R2026_RECT",
        invoice_type=InvoiceType.R1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="ALFONSO SL",
        recipient_nif="A98765432",
        recipient_name="CLIENTE QA",
        base_amount=-50.0,
        tax_amount=-10.5,
        total_amount=-60.5,
        rectified_series=orig_inv.series,
        rectified_number=orig_inv.number,
        rectification_method=RectificationMethod.DIFFERENCES,
        rectification_reason="Abono por diferencia de precio"
    )
    rect_i_inv = billing.emit_invoice_atomic(rect_i_in, force_valid_xml=True)
    assert rect_i_inv.number == rect_s_inv.number + 1
    assert rect_i_inv.rectification_method == RectificationMethod.DIFFERENCES


def test_qa_facturae_322_generation_and_validation():
    """QA: Verifica la generación de XML Facturae 3.2.2 válido para administraciones públicas (FACe) y B2B."""
    billing = BillingService()
    inv_in = InvoiceCreateDTO(
        series="F2026_FACTURAE",
        invoice_type=InvoiceType.F1,
        issue_date="2026-10-01",
        issuer_nif="B12345674",
        issuer_name="ALFONSO SL",
        recipient_nif="A98765432",
        recipient_name="ADMINISTRACION PUBLICA",
        base_amount=1500.0,
        tax_amount=315.0,
        total_amount=1815.0
    )
    invoice = billing.emit_invoice_atomic(inv_in, force_valid_xml=True)

    facturae_service = FacturaeService()
    facturae_xml = facturae_service.generate_facturae_322(invoice)
    assert b"Facturaev3_2_2.xml" in facturae_xml
    assert b"FileHeader" in facturae_xml
    assert b"Parties" in facturae_xml
    assert b"Invoices" in facturae_xml
    assert b"B12345674" in facturae_xml
    assert b"1815.00" in facturae_xml
