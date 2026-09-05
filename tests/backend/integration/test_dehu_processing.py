import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.dehu_service import DEHUService

# 1. Pruebas Unitarias del Parser de Metadatos de la DEHú
def test_dehu_metadata_parser():
    text_aeat = (
        "Agencia Estatal de Administración Tributaria (AEAT)\n"
        "Número de Referencia: REF-2026-9999\n"
        "Fecha de emisión: 27/08/2026\n"
        "Se notifica el requerimiento de documentación del IVA..."
    )
    
    text_tgss = (
        "Tesorería General de la Seguridad Social\n"
        "Nº Expediente: EXP-AFI-2026/102\n"
        "Fecha: 15-08-2026\n"
        "Aviso de discrepancias en ficheros de afiliación..."
    )
    
    # Evaluar AEAT
    meta_aeat = DEHUService.parse_metadata(text_aeat)
    assert "Agencia Estatal" in meta_aeat["organismo"]
    assert meta_aeat["expediente"] == "REF-2026-9999"
    assert meta_aeat["fecha_emision"] == "27/08/2026"
    
    # Evaluar TGSS
    meta_tgss = DEHUService.parse_metadata(text_tgss)
    assert "Seguridad Social" in meta_tgss["organismo"]
    assert meta_tgss["expediente"] == "EXP-AFI-2026/102"
    assert meta_tgss["fecha_emision"] == "15-08-2026"


# 2. Prueba Unitaria de Extracción de Texto de PDF (Mocking PdfReader)
def test_dehu_pdf_extraction():
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Contenido de texto extraído de la notificación oficial de DEHú."
    
    mock_reader = MagicMock()
    mock_reader.pages = [mock_page]
    
    with patch("app.domain.services.dehu_service.PdfReader", return_value=mock_reader):
        text = DEHUService.extract_text_from_pdf(b"fake_pdf_bytes")
        assert "Contenido de texto" in text


# 3. Prueba de Integración del Endpoint POST /compliance/dehu/upload
@pytest.mark.asyncio
async def test_dehu_upload_endpoint():
    client = TestClient(app)
    
    # Simular la respuesta de DEHUService para no invocar al LLM ni a pypdf
    mock_result = {
        "status": "ok",
        "metadata": {
            "organismo": "Agencia Estatal de Administración Tributaria (AEAT)",
            "expediente": "REF-TEST-999",
            "fecha_emision": "27/08/2026"
        },
        "text_preview": "Texto de prueba de la notificación...",
        "dictamen": "Dictamen legal simulado de Marcos para la notificación de prueba."
    }
    
    with patch("app.domain.services.dehu_service.DEHUService.process_and_analyze_notification", new_callable=AsyncMock) as mock_process:
        mock_process.return_value = mock_result
        
        # Enviar archivo de prueba
        files = {"file": ("notificacion_dehu.pdf", b"fake_pdf_data", "application/pdf")}
        response = client.post("/api/v1/compliance/dehu/upload", files=files)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["metadata"]["organismo"] == "Agencia Estatal de Administración Tributaria (AEAT)"
        assert "Dictamen" in data["dictamen"]
        
        # Verificar que se llamó con los bytes correctos
        mock_process.assert_called_once_with(b"fake_pdf_data")


# 4. Prueba del Endpoint con Formato No Válido
def test_dehu_upload_invalid_format():
    client = TestClient(app)
    
    # Enviar archivo txt en lugar de pdf
    files = {"file": ("documento.txt", b"fake_text_data", "text/plain")}
    response = client.post("/api/v1/compliance/dehu/upload", files=files)
    
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
