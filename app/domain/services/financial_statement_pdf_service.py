"""
Servicio generador de documentos PDF oficiales para Estados Financieros PGC PYMES (RD 1515/2007).
Apto para el depósito telemático de cuentas anuales en el Registro Mercantil.
"""

import io
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.domain.schemas import BalanceSheetDTO, IncomeStatementDTO


class FinancialStatementPdfService:
    """Genera informes financieros PDF oficiales según el PGC PYMES."""

    def generate_balance_sheet_pdf(self, balance: BalanceSheetDTO) -> bytes:
        """
        Emite el documento PDF formal del Balance de Situación para el depósito de cuentas.
        Bloquea la exportación si el balance no cumple la partida doble patrimonial.
        """
        if not balance.is_balanced:
            diff = balance.descuadre_forense.get("diferencia", "desconocida") if balance.descuadre_forense else "desconocida"
            raise ValueError(f"No se puede emitir el PDF: el balance contable está descuadrado (diferencia: {diff} €).")

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
        title_style = ParagraphStyle(
            'OfficialTitle',
            parent=styles['Heading1'],
            fontSize=16,
            leading=20,
            textColor=colors.HexColor('#0F172A'),
            alignment=1  # Center
        )
        subtitle_style = ParagraphStyle(
            'OfficialSubtitle',
            parent=styles['Normal'],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor('#475569'),
            alignment=1
        )
        section_style = ParagraphStyle(
            'MasaHeader',
            parent=styles['Heading2'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor('#1E293B'),
            fontName='Helvetica-Bold'
        )
        cell_style = ParagraphStyle(
            'TableCell',
            parent=styles['Normal'],
            fontSize=8,
            leading=10
        )
        cell_bold_style = ParagraphStyle(
            'TableCellBold',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            fontName='Helvetica-Bold'
        )

        story = []

        # Cabecera Oficial
        story.append(Paragraph("BALANCE DE SITUACIÓN NORMALIZADO", title_style))
        story.append(Paragraph("Plan General de Contabilidad de PYMES (RD 1515/2007) — Registro Mercantil", subtitle_style))
        story.append(Spacer(1, 10))

        # Metadatos del Informe
        meta_data = [
            [
                Paragraph(f"<b>Empresa / Tenant:</b> {balance.tenant_id}", cell_style),
                Paragraph(f"<b>Ejercicio Fiscal:</b> {balance.fiscal_year}", cell_style),
                Paragraph(f"<b>Fecha de Cierre:</b> {balance.fecha_cierre}", cell_style)
            ]
        ]
        meta_table = Table(meta_data, colWidths=[180, 160, 180])
        meta_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 15))

        # Tabla de Balance
        table_rows = [
            [
                Paragraph("<b>EPÍGRAFE / PARTIDA PATRIMONIAL</b>", cell_bold_style),
                Paragraph("<b>Cuentas</b>", cell_bold_style),
                Paragraph(f"<b>Ejercicio {balance.fiscal_year} (€)</b>", cell_bold_style),
                Paragraph(f"<b>Ejercicio {balance.fiscal_year - 1} (€)</b>", cell_bold_style)
            ]
        ]

        def _format_money(dec: Decimal) -> str:
            return f"{dec:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        # --- ACTIVO ---
        table_rows.append([Paragraph("<b>A) ACTIVO NO CORRIENTE</b>", cell_bold_style), "", "", ""])
        for l in balance.activo_no_corriente:
            table_rows.append([
                Paragraph(f"{l.epigrafe_codigo}. {l.epigrafe_nombre}", cell_style),
                Paragraph(", ".join(l.cuentas_asociadas[:3]) if l.cuentas_asociadas else "-", cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_actual), cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_anterior or Decimal("0.00")), cell_style)
            ])

        table_rows.append([Paragraph("<b>B) ACTIVO CORRIENTE</b>", cell_bold_style), "", "", ""])
        for l in balance.activo_corriente:
            table_rows.append([
                Paragraph(f"{l.epigrafe_codigo}. {l.epigrafe_nombre}", cell_style),
                Paragraph(", ".join(l.cuentas_asociadas[:3]) if l.cuentas_asociadas else "-", cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_actual), cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_anterior or Decimal("0.00")), cell_style)
            ])

        table_rows.append([
            Paragraph("<b>TOTAL ACTIVO (A + B)</b>", cell_bold_style),
            "",
            Paragraph(f"<b>{_format_money(balance.total_activo)}</b>", cell_bold_style),
            Paragraph(f"<b>{_format_money(Decimal('0.00'))}</b>", cell_bold_style)
        ])

        # --- PATRIMONIO NETO Y PASIVO ---
        table_rows.append([Paragraph("<b>A) PATRIMONIO NETO</b>", cell_bold_style), "", "", ""])
        for l in balance.patrimonio_neto:
            table_rows.append([
                Paragraph(f"{l.epigrafe_codigo}. {l.epigrafe_nombre}", cell_style),
                Paragraph(", ".join(l.cuentas_asociadas[:3]) if l.cuentas_asociadas else "-", cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_actual), cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_anterior or Decimal("0.00")), cell_style)
            ])

        table_rows.append([Paragraph("<b>B) PASIVO NO CORRIENTE</b>", cell_bold_style), "", "", ""])
        for l in balance.pasivo_no_corriente:
            table_rows.append([
                Paragraph(f"{l.epigrafe_codigo}. {l.epigrafe_nombre}", cell_style),
                Paragraph(", ".join(l.cuentas_asociadas[:3]) if l.cuentas_asociadas else "-", cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_actual), cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_anterior or Decimal("0.00")), cell_style)
            ])

        table_rows.append([Paragraph("<b>C) PASIVO CORRIENTE</b>", cell_bold_style), "", "", ""])
        for l in balance.pasivo_corriente:
            table_rows.append([
                Paragraph(f"{l.epigrafe_codigo}. {l.epigrafe_nombre}", cell_style),
                Paragraph(", ".join(l.cuentas_asociadas[:3]) if l.cuentas_asociadas else "-", cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_actual), cell_style),
                Paragraph(_format_money(l.saldo_ejercicio_anterior or Decimal("0.00")), cell_style)
            ])

        table_rows.append([
            Paragraph("<b>TOTAL PASIVO Y PATRIMONIO NETO (A + B + C)</b>", cell_bold_style),
            "",
            Paragraph(f"<b>{_format_money(balance.total_pasivo_y_patrimonio_neto)}</b>", cell_bold_style),
            Paragraph(f"<b>{_format_money(Decimal('0.00'))}</b>", cell_bold_style)
        ])

        balance_table = Table(table_rows, colWidths=[240, 100, 90, 90])
        balance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, len(balance.activo_no_corriente) + len(balance.activo_corriente) + 2), (-1, len(balance.activo_no_corriente) + len(balance.activo_corriente) + 2), colors.HexColor('#F1F5F9')),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#F1F5F9')),
        ]))
        story.append(balance_table)
        story.append(Spacer(1, 15))

        # Certificación de Cuadre
        cert_text = (
            "<b>CERTIFICACIÓN OFICIAL DE CUADRE CONTABLE:</b> Se certifica la exactitud matemática de los saldos "
            "conforme al Real Decreto 1515/2007 (PGC PYMES). Ecuación patrimonial verificada: "
            f"Total Activo ({_format_money(balance.total_activo)} €) = "
            f"Total Pasivo y Patrimonio Neto ({_format_money(balance.total_pasivo_y_patrimonio_neto)} €) "
            "con descuadre 0,00 €."
        )
        cert_data = [[Paragraph(cert_text, cell_style)]]
        cert_table = Table(cert_data, colWidths=[520])
        cert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#DCFCE7')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#16A34A')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(cert_table)

        doc.build(story)
        return buffer.getvalue()
