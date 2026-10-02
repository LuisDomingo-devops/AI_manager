from decimal import Decimal
import pytest
from app.domain.services.invoice_ocr_parser import InvoiceOCRParser


def test_parse_standard_single_vat_invoice():
    """Factura ordinaria estándar con tipo general de IVA (21%)."""
    parser = InvoiceOCRParser()
    text = """
    TELEFÓNICA DE ESPAÑA S.A.U.
    CIF: A28015865
    Factura Nº: TE-2026-90412
    Fecha de emisión: 15/05/2026
    
    Concepto: Conectividad Fibra Óptica 1Gbps y telefonía fija
    Base Imponible: 100.00 €
    IVA (21%): 21.00 €
    TOTAL A PAGAR: 121.00 €
    """
    
    result = parser.parse_invoice_text(
        text=text,
        source_email_id="msg_001",
        pdf_path="data/invoices_received/2026/05/te_2026.pdf"
    )

    assert result.sender_nif == "A28015865"
    assert result.invoice_number == "TE-2026-90412"
    assert result.issue_date == "2026-05-15"
    assert result.total_amount == Decimal("121.00")
    assert result.confidence_score >= 0.85
    assert len(result.taxes) == 1
    assert result.taxes[0].tax_rate == Decimal("21.00")
    assert result.taxes[0].tax_base == Decimal("100.00")
    assert result.taxes[0].tax_amount == Decimal("21.00")
    assert result.irpf_retention_amount == Decimal("0.00")


def test_parse_multi_vat_invoice():
    """Factura con múltiples tipos de IVA (10% reducido y 21% general)."""
    parser = InvoiceOCRParser()
    text = """
    HOTEL Y RESTAURANTE MADRID S.L.
    NIF: B84019283
    Factura: H-2026/0491
    Fecha: 2026-06-20
    
    Servicios de alojamiento y desayuno (10%):
    Base: 200.00 €  Cuota IVA 10%: 20.00 €
    Servicios de alquiler de sala y equipos audiovisuales (21%):
    Base: 100.00 €  Cuota IVA 21%: 21.00 €
    
    TOTAL FACTURA: 341.00 €
    """

    result = parser.parse_invoice_text(
        text=text,
        source_email_id="msg_002",
        pdf_path="data/invoices_received/2026/06/hotel.pdf"
    )

    assert result.sender_nif == "B84019283"
    assert result.invoice_number == "H-2026/0491"
    assert result.issue_date == "2026-06-20"
    assert result.total_amount == Decimal("341.00")
    assert result.confidence_score >= 0.85
    assert len(result.taxes) == 2
    
    total_base = sum(t.tax_base for t in result.taxes)
    total_vat = sum(t.tax_amount for t in result.taxes)
    assert total_base == Decimal("300.00")
    assert total_vat == Decimal("41.00")
    assert total_base + total_vat == result.total_amount


def test_parse_professional_invoice_with_irpf():
    """Factura de profesional autónomo con IVA (21%) y retención de IRPF (15%)."""
    parser = InvoiceOCRParser()
    text = """
    JUAN GARCIA PEREZ
    NIF: 45678901B
    Número de Factura: PROF-2026-11
    Fecha expedición: 10-04-2026
    
    Honorarios asesoría jurídica mercantil:
    Base imponible: 1000.00 €
    IVA Repercutido (21%): 210.00 €
    Retención IRPF (15%): -150.00 €
    TOTAL LÍQUIDO A PERCIBIR: 1060.00 €
    """

    result = parser.parse_invoice_text(
        text=text,
        source_email_id="msg_003",
        pdf_path="data/invoices_received/2026/04/prof.pdf"
    )

    assert result.sender_nif == "45678901B"
    assert result.invoice_number == "PROF-2026-11"
    assert result.issue_date == "2026-04-10"
    assert result.total_amount == Decimal("1060.00")
    assert result.confidence_score >= 0.85
    assert result.irpf_retention_rate == Decimal("15.00")
    assert result.irpf_retention_amount == Decimal("150.00")
    
    # Cuadre matemático: Base + IVA - IRPF == Total
    calc_total = result.taxes[0].tax_base + result.taxes[0].tax_amount - result.irpf_retention_amount
    assert calc_total == result.total_amount


def test_parse_unbalanced_text_penalizes_confidence():
    """Texto con descuadre matemático penaliza la puntuación de confianza."""
    parser = InvoiceOCRParser()
    text = """
    PROVEEDOR DESCUADRADO S.L.
    CIF: B12345678
    Factura: DESC-001
    Fecha: 2026-01-01
    Base imponible: 100.00 €
    IVA (21%): 21.00 €
    TOTAL: 999.00 €
    """

    result = parser.parse_invoice_text(
        text=text,
        source_email_id="msg_004",
        pdf_path="data/invoices_received/2026/01/desc.pdf"
    )

    # Debido a descuadre severo entre 121.00 y 999.00
    assert result.confidence_score < 0.85
