"""
Generador de Documentos Oficiales en PDF (Declaración Responsable del SIF).
Conforme al Artículo 13 del Real Decreto 1007/2023 y Orden HAC/1177/2024.
"""

import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

from app.config import settings


def generate_declaracion_responsable(
    razon_social: str,
    nif: str,
    modalidad_verifactu: bool = True
) -> bytes:
    """
    Genera en formato PDF la Declaración Responsable obligatoria del Sistema Informático de Facturación (SIF)
    conforme al Artículo 13 del Real Decreto 1007/2023 y la Orden HAC/1177/2024.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=36
    )
    styles = getSampleStyleSheet()

    # Estilos tipográficos premium
    title_style = ParagraphStyle(
        "SIFTitle",
        parent=styles["Title"],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#0F172A"),
        alignment=1,
        fontName="Helvetica-Bold"
    )
    subtitle_style = ParagraphStyle(
        "SIFSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#475569"),
        alignment=1,
        fontName="Helvetica-Oblique"
    )
    body_style = ParagraphStyle(
        "SIFBody",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#1E293B"),
        fontName="Helvetica"
    )
    bold_style = ParagraphStyle(
        "SIFBold",
        parent=styles["Normal"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#0F172A"),
        fontName="Helvetica-Bold"
    )

    story = []

    # Encabezado
    story.append(Paragraph("DECLARACIÓN RESPONSABLE DEL SISTEMA INFORMÁTICO DE FACTURACIÓN (SIF)", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Conforme al Artículo 13 del Real Decreto 1007/2023 y la Orden HAC/1177/2024", subtitle_style))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#CBD5E1"), spaceAfter=14))

    # 1. Datos del Productor del Software
    sif_name = getattr(settings, "SIF_SOFTWARE_NAME", "Alfonso Autónomo SIF")
    sif_ver = getattr(settings, "SIF_VERSION", "2026.1.0")
    prod_nif = getattr(settings, "ALFONSO_SIF_PRODUCER_NIF", "B00000000")
    prod_name = "Alfonso AI Solutions S.L."

    story.append(Paragraph("<b>1. IDENTIFICACIÓN DEL SISTEMA INFORMÁTICO Y DE SU PRODUCTOR:</b>", bold_style))
    story.append(Spacer(1, 4))
    info_prod = (
        f"• <b>Denominación Comercial del SIF:</b> {sif_name}<br/>"
        f"• <b>Versión Certificada del Software:</b> {sif_ver}<br/>"
        f"• <b>Productor / Desarrollador:</b> {prod_name}<br/>"
        f"• <b>NIF del Productor:</b> {prod_nif}<br/>"
        f"• <b>Modalidad Operativa:</b> {'Sistema de Emisión de Facturas Verificables (VERI*FACTU)' if modalidad_verifactu else 'Sistema Informático de Facturación (No Verifactu)'}"
    )
    story.append(Paragraph(info_prod, body_style))
    story.append(Spacer(1, 12))

    # 2. Datos del Obligado Tributario
    story.append(Paragraph("<b>2. IDENTIFICACIÓN DEL OBLIGADO TRIBUTARIO USUARIO DEL SISTEMA:</b>", bold_style))
    story.append(Spacer(1, 4))
    info_user = (
        f"• <b>Nombre o Razón Social:</b> {razon_social}<br/>"
        f"• <b>NIF / NIE:</b> {nif}"
    )
    story.append(Paragraph(info_user, body_style))
    story.append(Spacer(1, 14))

    # 3. Declaración de Conformidad
    story.append(Paragraph("<b>3. DECLARACIÓN FORMAL DE CONFORMIDAD Y CUMPLIMIENTO REGULATORIO:</b>", bold_style))
    story.append(Spacer(1, 6))

    declaracion_texto = (
        "El productor del sistema informático y el obligado tributario firmante manifiestan y certifican que "
        f"el sistema <b>'{sif_name}' (versión {sif_ver})</b> cumple de forma estricta y exhaustiva con las especificaciones "
        "establecidas en el <b>artículo 29.2.j) de la Ley 58/2003, de 17 de diciembre, General Tributaria</b>, "
        "en el <b>Real Decreto 1007/2023, de 5 de diciembre</b> (Reglamento de requisitos de los sistemas informáticos "
        "de facturación) y en la <b>Orden HAC/1177/2024, de 17 de octubre</b>.<br/><br/>"
        "En particular, se certifica que el sistema informático:<br/>"
        "<b>a) Integridad e Inalterabilidad:</b> Genera de manera automática e irreversible un registro de facturación de alta "
        "con huella digital SHA-256 encadenada criptográficamente con el registro anterior, imposibilitando la modificación, "
        "interpolación, borrado o alteración de facturas ya consolidadas sin dejar traza auditable.<br/>"
        "<b>b) Ausencia de Capacidades de Ocultación (Anti Doble Uso):</b> No dispone de funcionalidades, códigos ocultos ni comandos "
        "que permitan llevar contabilidades paralelas, omitir facturación, manipular cifras tributarias o alterar registros contables "
        "(cumplimiento de la Ley 11/2021 de medidas de prevención y lucha contra el fraude fiscal).<br/>"
        "<b>c) Conservación y Trazabilidad:</b> Mantiene un Libro de Eventos del SIF (sif_event_log) firmado digitalmente que documenta "
        "las anomalías de integridad, operaciones de backup/restauración, cortes de red y ciclos de arranque y parada del software.<br/>"
        "<b>d) Legibilidad y Formatos Estándar:</b> Permite la exportación inmediata y estructurada de los registros de facturación "
        "en formato XML validado contra el esquema oficial 'RegFactuSistemaFacturacion.xsd' ante requerimiento de la Inspección Tributaria."
    )
    story.append(Paragraph(declaracion_texto, body_style))
    story.append(Spacer(1, 18))

    # 4. Pie de firma y fecha
    fecha_emision = datetime.now().strftime("%d de %m de %Y a las %H:%M:%S")
    pie_texto = (
        f"<b>Fecha y Hora Oficial de Emisión de la Declaración:</b> {fecha_emision} (Huso horario peninsular español).<br/>"
        "Esta declaración se expide a los efectos oportunos y queda a disposición inmediata de los órganos de la "
        "Administración Tributaria conforme al artículo 13.3 del Real Decreto 1007/2023."
    )
    story.append(Paragraph(pie_texto, body_style))
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceAfter=14))

    doc.build(story)
    return buffer.getvalue()
