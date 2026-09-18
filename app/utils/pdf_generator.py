import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

def generate_declaracion_responsable(razon_social: str, nif: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
    styles = getSampleStyleSheet()
    Story = []
    
    title = Paragraph("<b>DECLARACIÓN RESPONSABLE DEL SISTEMA INFORMÁTICO (VERIFACTU)</b>", styles["Title"])
    Story.append(title)
    Story.append(Spacer(1, 24))
    
    text = (
        f"El obligado tributario <b>{razon_social}</b> con NIF <b>{nif}</b>, "
        "declara bajo su responsabilidad que el software de facturación 'Alfonso Autónomo SIF' "
        "que utiliza para la emisión de sus facturas cumple con los requisitos establecidos en "
        "el artículo 29.2.j) de la Ley 58/2003, de 17 de diciembre, General Tributaria, "
        "así como en el Reglamento que establece los requisitos que deben adoptar los sistemas y "
        "programas informáticos o electrónicos que soporten los procesos de facturación "
        "(Real Decreto 1007/2023, de 5 de diciembre) y en la Orden HAC/1177/2024.<br/><br/>"
        "Asimismo, declara que el sistema garantiza la integridad, conservación, accesibilidad, "
        "legibilidad, trazabilidad e inalterabilidad de los registros de facturación, sin interpolaciones, "
        "omisiones o alteraciones de las que no quede la debida anotación en los mismos (encadenamiento criptográfico)."
    )
    
    p = Paragraph(text, styles["Normal"])
    Story.append(p)
    Story.append(Spacer(1, 48))
    
    date_text = Paragraph(f"Fecha de emisión y descarga: {datetime.now().strftime('%d de %m de %Y a las %H:%M:%S')}", styles["Normal"])
    Story.append(date_text)
    
    doc.build(Story)
    return buffer.getvalue()
