from pypdf import PdfReader, PdfWriter
import io
from typing import Dict, Any

def fill_aeat_pdf_template(template_path: str, data: Dict[str, Any]) -> bytes:
    """
    Lee una plantilla PDF (ej: Modelo 303), rellena los campos de formulario
    AcroForm definidos con los valores del diccionario `data`,
    y devuelve el PDF resultante en formato bytes.
    """
    reader = PdfReader(template_path)
    writer = PdfWriter()
    
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    
    # 1. Crear el overlay con ReportLab
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica", 10)
    
    # Escribir los datos en coordenadas aproximadas (esto requerirá ajuste según modelo)
    # Por ahora simplemente mostramos los datos provistos en un listado a la izquierda.
    y = 800
    for key, value in data.items():
        c.drawString(50, y, f"{key}: {value}")
        y -= 20
        
    c.save()
    packet.seek(0)
    
    # 2. Leer el overlay y la plantilla
    new_pdf = PdfReader(packet)
    template_pdf = PdfReader(template_path)
    writer = PdfWriter()
    
    # 3. Superponer la primera página
    page = template_pdf.pages[0]
    # Si tenemos overlay para más páginas habría que iterar, aquí lo hacemos sobre la primera
    if len(new_pdf.pages) > 0:
        page.merge_page(new_pdf.pages[0])
    writer.add_page(page)
    
    # Añadir el resto de páginas sin modificar
    for i in range(1, len(template_pdf.pages)):
        writer.add_page(template_pdf.pages[i])
        
    # Escribimos el resultado a bytes
    output_stream = io.BytesIO()
    writer.write(output_stream)
    
    return output_stream.getvalue()
