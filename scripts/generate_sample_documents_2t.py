"""
GENERADOR DE DOCUMENTOS FÍSICOS (PDF, JPG, PNG) PARA LA SIMULACIÓN DEL 2T 2026
Genera 16 facturas, tickets, recibos de alquiler, seguros y nóminas con diseño formal.
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "trimestre_2t2026"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_pdf_invoice(filename, invoice_num, date_str, issuer_name, issuer_nif, receiver_name, receiver_nif, concept, base, iva_pct, iva_amt, irpf_pct, irpf_amt, total, doc_type="FACTURA"):
    filepath = OUTPUT_DIR / filename
    c = canvas.Canvas(str(filepath), pagesize=A4)
    width, height = A4

    # Cabecera
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, height - 50, doc_type)
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, f"Número: {invoice_num}")
    c.drawString(50, height - 85, f"Fecha: {date_str}")

    # Datos Emisor y Receptor
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 120, "DATOS DEL EMISOR / PROVEEDOR:")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 135, f"Razón Social: {issuer_name}")
    c.drawString(50, height - 150, f"NIF / CIF: {issuer_nif}")

    c.setFont("Helvetica-Bold", 12)
    c.drawString(300, height - 120, "DATOS DEL RECEPTOR / CLIENTE:")
    c.setFont("Helvetica", 10)
    c.drawString(300, height - 135, f"Razón Social: {receiver_name}")
    c.drawString(300, height - 150, f"NIF / CIF: {receiver_nif}")

    # Línea separadora
    c.line(50, height - 170, width - 50, height - 170)

    # Detalle del concepto
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, height - 190, "DESCRIPCIÓN / CONCEPTO")
    c.drawString(450, height - 190, "IMPORTE")
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 210, concept)
    c.drawString(450, height - 210, f"{base:,.2f} €")

    # Línea separadora
    c.line(50, height - 240, width - 50, height - 240)

    # Desglose de Totales
    y = height - 265
    c.setFont("Helvetica", 10)
    c.drawString(320, y, f"Base Imponible:")
    c.drawString(450, y, f"{base:,.2f} €")
    
    y -= 18
    c.drawString(320, y, f"IVA ({iva_pct:.1f}%):")
    c.drawString(450, y, f"{iva_amt:,.2f} €")

    if irpf_amt > 0:
        y -= 18
        c.drawString(320, y, f"Retención IRPF ({irpf_pct:.1f}%):")
        c.drawString(450, y, f"-{irpf_amt:,.2f} €")

    y -= 25
    c.setFont("Helvetica-Bold", 12)
    c.drawString(320, y, "TOTAL A PAGAR:")
    c.drawString(450, y, f"{total:,.2f} €")

    # Pie de página
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(50, 40, "Documento fiscal generado automáticamente para el Sistema Informático de Facturación Alfonso.")

    c.save()
    print(f"[*] PDF generado: {filename}")


def create_image_invoice(filename, invoice_num, date_str, issuer_name, issuer_nif, receiver_name, receiver_nif, concept, base, iva_pct, iva_amt, irpf_pct, irpf_amt, total, doc_type="FACTURA"):
    filepath = OUTPUT_DIR / filename
    img = Image.new("RGB", (900, 700), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("arial.ttf", 26)
        font_bold = ImageFont.truetype("arialbd.ttf", 16)
        font_normal = ImageFont.truetype("arial.ttf", 15)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except Exception:
        font_large = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.text((40, 30), f"{doc_type} - {invoice_num}", fill=(0, 0, 0), font=font_large)
    draw.text((40, 70), f"Fecha de emisión: {date_str}", fill=(50, 50, 50), font=font_normal)

    # Emisor
    draw.text((40, 120), "EMISOR / PROVEEDOR:", fill=(0, 0, 0), font=font_bold)
    draw.text((40, 145), f"Nombre: {issuer_name}", fill=(0, 0, 0), font=font_normal)
    draw.text((40, 170), f"NIF: {issuer_nif}", fill=(0, 0, 0), font=font_normal)

    # Receptor
    draw.text((480, 120), "RECEPTOR / CLIENTE:", fill=(0, 0, 0), font=font_bold)
    draw.text((480, 145), f"Nombre: {receiver_name}", fill=(0, 0, 0), font=font_normal)
    draw.text((480, 170), f"NIF: {receiver_nif}", fill=(0, 0, 0), font=font_normal)

    draw.line([(40, 210), (860, 210)], fill=(180, 180, 180), width=2)

    # Concepto
    draw.text((40, 230), "CONCEPTO", fill=(0, 0, 0), font=font_bold)
    draw.text((700, 230), "IMPORTE", fill=(0, 0, 0), font=font_bold)
    draw.text((40, 260), concept, fill=(0, 0, 0), font=font_normal)
    draw.text((700, 260), f"{base:,.2f} EUR", fill=(0, 0, 0), font=font_normal)

    draw.line([(40, 300), (860, 300)], fill=(180, 180, 180), width=2)

    # Desglose
    draw.text((500, 330), "Base Imponible:", fill=(0, 0, 0), font=font_normal)
    draw.text((700, 330), f"{base:,.2f} EUR", fill=(0, 0, 0), font=font_normal)

    draw.text((500, 360), f"IVA ({iva_pct:.1f}%):", fill=(0, 0, 0), font=font_normal)
    draw.text((700, 360), f"{iva_amt:,.2f} EUR", fill=(0, 0, 0), font=font_normal)

    y_total = 400
    if irpf_amt > 0:
        draw.text((500, y_total), f"Retención IRPF ({irpf_pct:.1f}%):", fill=(0, 0, 0), font=font_normal)
        draw.text((700, y_total), f"-{irpf_amt:,.2f} EUR", fill=(0, 0, 0), font=font_normal)
        y_total += 35

    draw.text((40, 650), "Documento para validación tributaria y OCR en Alfonso.", fill=(100, 100, 100), font=font_small)

    full_text = f"""{doc_type}
Número: {invoice_num}
Fecha: {date_str}
DATOS DEL EMISOR / PROVEEDOR:
Razón Social: {issuer_name}
NIF / CIF: {issuer_nif}

DATOS DEL RECEPTOR / CLIENTE:
Razón Social: {receiver_name}
NIF / CIF: {receiver_nif}

DESCRIPCIÓN / CONCEPTO: {concept}
Base Imponible: {base:.2f} €
IVA ({iva_pct:.1f}%): {iva_amt:.2f} €
"""
    if irpf_amt > 0:
        full_text += f"Retención IRPF ({irpf_pct:.1f}%): -{irpf_amt:.2f} €\n"
    full_text += f"TOTAL A PAGAR: {total:.2f} €"

    if filename.lower().endswith(".png"):
        from PIL import PngImagePlugin
        meta = PngImagePlugin.PngInfo()
        meta.add_text("description", full_text)
        img.save(str(filepath), pnginfo=meta)
    elif filename.lower().endswith(".jpg") or filename.lower().endswith(".jpeg"):
        img.save(str(filepath), comment=full_text.encode("utf-8"))
    else:
        img.save(str(filepath))

    print(f"[*] Imagen generada: {filename}")


def main():
    print("=" * 80)
    print("  GENERANDO 16 DOCUMENTOS EN FORMATOS REALES (PDF, JPG, PNG) - 2T 2026")
    print("=" * 80)

    # 1. Facturas Emitidas (Ingresos Cobrados)
    # FAC-2026-004.pdf
    create_pdf_invoice("FAC-2026-004.pdf", "FAC-2026-004", "15/04/2026", "LUIS DOMINGO", "12345678Z", "GAMMA TECH S.L.", "B11223344", "Consultoría en Inteligencia Artificial y Cloud", 2500.0, 21.0, 525.0, 0.0, 0.0, 3025.0)

    # FAC-2026-005.jpg (Con IRPF)
    create_image_invoice("FAC-2026-005.jpg", "FAC-2026-005", "10/05/2026", "LUIS DOMINGO", "12345678Z", "DELTA STUDIO S.A.", "A58818501", "Desarrollo y diseño de plataforma interactiva", 1800.0, 21.0, 378.0, 15.0, 270.0, 1908.0)

    # FAC-2026-006.pdf
    create_pdf_invoice("FAC-2026-006.pdf", "FAC-2026-006", "22/05/2026", "LUIS DOMINGO", "12345678Z", "EPSILON ANALYTICS S.L.", "B98765432", "Auditoría de ciberseguridad y pentesting", 4000.0, 21.0, 840.0, 0.0, 0.0, 4840.0)

    # FAC-2026-007.png
    create_image_invoice("FAC-2026-007.png", "FAC-2026-007", "18/06/2026", "LUIS DOMINGO", "12345678Z", "ZETA SYSTEMS S.L.", "B55667788", "Mantenimiento preventivo e infraestructura DevOps", 1200.0, 21.0, 252.0, 0.0, 0.0, 1452.0)

    # 2. Facturas de Proveedores y Gastos
    # EXP-2026-004.pdf (Cloud)
    create_pdf_invoice("EXP-2026-004.pdf", "EXP-2026-004", "20/04/2026", "AWS CLOUD IBERIA S.L.", "B87654321", "LUIS DOMINGO", "12345678Z", "Servicios de computación en la nube y almacenamiento", 400.0, 21.0, 84.0, 0.0, 0.0, 484.0, doc_type="FACTURA DE GASTO")

    # EXP-2026-005.jpg (Desplazamientos)
    create_image_invoice("EXP-2026-005.jpg", "EXP-2026-005", "05/05/2026", "REPSOL ESTACIONES S.A.", "A28000000", "LUIS DOMINGO", "12345678Z", "Combustible y desplazamientos a clientes de consultoría", 150.0, 21.0, 31.50, 0.0, 0.0, 181.50, doc_type="TICKET FACTURA")

    # EXP-2026-006.pdf (Abogado con IRPF)
    create_pdf_invoice("EXP-2026-006.pdf", "EXP-2026-006", "15/05/2026", "ABOGADOS & ASESORES S.L.", "B33445566", "LUIS DOMINGO", "12345678Z", "Honorarios de asesoría jurídica mercantil y contratos", 600.0, 21.0, 126.0, 15.0, 90.0, 636.0, doc_type="FACTURA PROFESIONAL")

    # EXP-2026-007.png (Hardware)
    create_image_invoice("EXP-2026-007.png", "EXP-2026-007", "02/06/2026", "PCCOMPONENTES S.L.", "B73650600", "LUIS DOMINGO", "12345678Z", "Periféricos informáticos y memoria RAM servidores", 250.0, 21.0, 52.50, 0.0, 0.0, 302.50, doc_type="FACTURA COMPRA")

    # EXP-2026-008.pdf (Fibra)
    create_pdf_invoice("EXP-2026-008.pdf", "EXP-2026-008", "25/06/2026", "TELEFONICA EMPRESAS S.A.", "A28015865", "LUIS DOMINGO", "12345678Z", "Conexión a Internet Fibra Óptica 1Gbps oficina", 100.0, 21.0, 21.0, 0.0, 0.0, 121.0, doc_type="FACTURA TELECOM")

    # 3. Alquileres de Oficina (Modelo 115)
    create_pdf_invoice("ALQ-2026-04.pdf", "ALQ-2026-04", "05/04/2026", "INMOBILIARIA CENTRO S.L.", "B44556677", "LUIS DOMINGO", "12345678Z", "Alquiler mensual oficina comercial - Abril 2026", 800.0, 21.0, 168.0, 19.0, 152.0, 816.0, doc_type="RECIBO ARRENDAMIENTO")
    create_pdf_invoice("ALQ-2026-05.pdf", "ALQ-2026-05", "05/05/2026", "INMOBILIARIA CENTRO S.L.", "B44556677", "LUIS DOMINGO", "12345678Z", "Alquiler mensual oficina comercial - Mayo 2026", 800.0, 21.0, 168.0, 19.0, 152.0, 816.0, doc_type="RECIBO ARRENDAMIENTO")
    create_pdf_invoice("ALQ-2026-06.pdf", "ALQ-2026-06", "05/06/2026", "INMOBILIARIA CENTRO S.L.", "B44556677", "LUIS DOMINGO", "12345678Z", "Alquiler mensual oficina comercial - Junio 2026", 800.0, 21.0, 168.0, 19.0, 152.0, 816.0, doc_type="RECIBO ARRENDAMIENTO")

    # 4. Seguro Exento de IVA
    create_pdf_invoice("SEG-2026-02.pdf", "SEG-2026-02", "10/04/2026", "MAPFRE SEGUROS S.A.", "A28006797", "LUIS DOMINGO", "12345678Z", "Prima Seguro Ciberriesgos y RC Profesional 2T (Exento Art. 20 LIVA)", 300.0, 0.0, 0.0, 0.0, 0.0, 300.0, doc_type="POLIZA DE SEGURO")

    # 5. Nóminas de Empleados (Modelo 111 y Seg. Social)
    create_pdf_invoice("NOM-2026-04.pdf", "NOM-2026-04", "30/04/2026", "CARLOS SÁNCHEZ GÓMEZ", "87654321A", "LUIS DOMINGO", "12345678Z", "Nómina Abril 2026: Sueldo Bruto 1.200€ | SS Empresa 378€ | IRPF 10% 120€", 1578.0, 0.0, 0.0, 10.0, 120.0, 1578.0, doc_type="RECIBO DE NÓMINA")
    create_pdf_invoice("NOM-2026-05.pdf", "NOM-2026-05", "31/05/2026", "CARLOS SÁNCHEZ GÓMEZ", "87654321A", "LUIS DOMINGO", "12345678Z", "Nómina Mayo 2026: Sueldo Bruto 1.200€ | SS Empresa 378€ | IRPF 10% 120€", 1578.0, 0.0, 0.0, 10.0, 120.0, 1578.0, doc_type="RECIBO DE NÓMINA")
    create_pdf_invoice("NOM-2026-06.pdf", "NOM-2026-06", "30/06/2026", "CARLOS SÁNCHEZ GÓMEZ", "87654321A", "LUIS DOMINGO", "12345678Z", "Nómina Junio 2026: Sueldo Bruto 1.200€ | SS Empresa 378€ | IRPF 10% 120€", 1578.0, 0.0, 0.0, 10.0, 120.0, 1578.0, doc_type="RECIBO DE NÓMINA")

    print("\n[+] 16 Documentos generados correctamente en: docs/trimestre_2t2026/")


if __name__ == "__main__":
    main()
