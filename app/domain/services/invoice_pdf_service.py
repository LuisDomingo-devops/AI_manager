"""
Servicio generador de PDF para facturas emitidas bajo Veri*Factu.
Incorpora código QR oficial y leyenda reglamentaria obligatoria.
"""

import io
import qrcode
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from app.domain.models.billing import InvoiceDTO


class InvoicePDFService:
    """Genera documentos PDF fiscales conformes con los requisitos de la AEAT."""

    def generate_invoice_pdf(self, invoice: InvoiceDTO) -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        styles = getSampleStyleSheet()
        story = []

        # Título y Tipo
        tipo_desc = "FACTURA ORDINARIA" if invoice.invoice_type.value == "F1" else f"FACTURA RECTIFICATIVA ({invoice.invoice_type.value})"
        story.append(Paragraph(f"<b>{tipo_desc}</b>", styles["Title"]))
        story.append(Spacer(1, 10))

        # Encabezado: Emisor y Receptor
        invoice_num_str = f"{invoice.series}-{invoice.number:04d}"
        header_data = [
            [
                Paragraph(f"<b>EMISOR:</b><br/>{invoice.issuer_name}<br/>NIF: {invoice.issuer_nif}", styles["Normal"]),
                Paragraph(f"<b>FACTURA Nº:</b> {invoice_num_str}<br/><b>FECHA:</b> {invoice.issue_date}", styles["Normal"])
            ],
            [
                Paragraph(f"<b>RECEPTOR:</b><br/>{invoice.recipient_name or 'CONSUMIDOR FINAL'}<br/>NIF: {invoice.recipient_nif or 'NIF_NO_APLICA'}", styles["Normal"]),
                Paragraph(f"<b>ESTADO:</b> {invoice.status.value}", styles["Normal"])
            ]
        ]
        header_table = Table(header_data, colWidths=[260, 260])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 15))

        # Si es rectificativa, incluir referencia
        if invoice.rectified_series and invoice.rectified_number:
            rect_text = f"<b>Factura Rectificada:</b> {invoice.rectified_series}-{invoice.rectified_number:04d} | <b>Motivo:</b> {invoice.rectification_reason or 'No especificado'}"
            story.append(Paragraph(rect_text, styles["Normal"]))
            story.append(Spacer(1, 10))

        # Totales
        totals_data = [
            ["Base Imponible:", f"{invoice.base_amount:.2f} €"],
            ["Cuota IVA (21%):", f"{invoice.tax_amount:.2f} €"],
            ["Total Factura:", f"{invoice.total_amount:.2f} €"],
        ]
        totals_table = Table(totals_data, colWidths=[150, 100], hAlign='RIGHT')
        totals_table.setStyle(TableStyle([
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('LINEABOVE', (0, 2), (-1, 2), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ]))
        story.append(totals_table)
        story.append(Spacer(1, 25))

        # Generar imagen QR en memoria
        qr_url = ""
        if invoice.hash_record and invoice.hash_record.qr_url:
            qr_url = invoice.hash_record.qr_url
        else:
            qr_url = f"https://www.agenciatributaria.gob.es/wlpl/TIKE-CONT/ValidarQR?nif={invoice.issuer_nif}&numserie={invoice_num_str}&fecha={invoice.issue_date}&importe={invoice.total_amount:.2f}"

        qr_img = qrcode.make(qr_url)
        qr_buffer = io.BytesIO()
        qr_img.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        # Pie con QR y Leyenda legal obligatoria
        legal_text = (
            "<b>VERI*FACTU</b><br/>"
            "Factura verificable en la sede electrónica de la AEAT.<br/>"
            "Sistema Informático de Facturación conforme al RD 1007/2023 y la Orden HAC/1177/2024.<br/>"
            f"<font size='7'>Huella: {invoice.hash_record.current_hash if invoice.hash_record else 'N/A'}</font>"
        )

        footer_data = [
            [
                Image(qr_buffer, width=80, height=80),
                Paragraph(legal_text, styles["Normal"])
            ]
        ]
        footer_table = Table(footer_data, colWidths=[90, 430])
        footer_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        story.append(footer_table)

        doc.build(story)
        return buffer.getvalue()

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extrae el contenido textual del PDF para aserciones de pruebas y auditoría."""
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
