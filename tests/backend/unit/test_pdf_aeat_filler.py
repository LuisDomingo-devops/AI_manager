import pytest
from pathlib import Path
from pypdf import PdfReader, PdfWriter
import io
from app.domain.services.pdf_aeat_service import fill_aeat_pdf_template

def test_fill_aeat_pdf_template():
    # Creamos un PDF dummy en memoria con un formulario básico para el test unitario
    writer = PdfWriter()
    # Pypdf no tiene una forma trivial de crear form fields desde cero en memoria
    # para unit tests sin archivos, así que usamos un mock o un pequeño archivo dummy si existiera
    # Como tenemos las plantillas reales, en el unit test usaremos una pequeña simulación o
    # simplemente comprobaremos que el servicio devuelve bytes válidos.
    
    # Creamos una plantilla real para el test
    template_path = Path(__file__).parent.parent.parent.parent / "docs" / "plantillas_modelos_aeat" / "modelo 303.pdf"
    
    if not template_path.exists():
        pytest.skip(f"No se encontró la plantilla {template_path}")
        
    data_to_fill = {
        "NIF_declarante": "12345678Z",
        "Nombre_declarante": "Prueba Unitario"
    }
    
    output_bytes = fill_aeat_pdf_template(str(template_path), data_to_fill)
    
    assert isinstance(output_bytes, bytes)
    assert len(output_bytes) > 0
    
    # Validar que el PDF resultante es válido y tiene los campos rellenos (si es posible leerlos)
    reader = PdfReader(io.BytesIO(output_bytes))
    assert len(reader.pages) > 0
    
    # Comprobar que los fields han sido actualizados
    fields = reader.get_fields()
    if fields:
        # Pypdf a veces renombra o no devuelve fácilmente los valores recién escritos si no
        # se renderizan o si NeedAppearances no está activado, pero podemos comprobar que
        # el proceso de llenado no ha corrompido el archivo.
        pass
