import pytest
import base64
import os
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.document_customization_service import DocumentCustomizationService
from app.adapters.document_customization import SqliteDocumentCustomizationAdapter
from app.adapters.memory.memory import _get_connection, tenant_context
from app.tools.server.billing_tools import generate_invoice_pdf, create_quote, get_quotes

# Imagen minimalista de prueba en formato base64 (un píxel transparente en PNG)
MOCK_LOGO_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

@pytest.fixture(scope="module")
def client():
    headers = {"X-API-Key": "test_api_key_default"}
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c

def test_hex_to_rgb():
    service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
    
    # Test conversión correcta
    r, g, b = service.hex_to_rgb("#1E293B")
    assert round(r, 3) == round(0.1176, 3)
    assert round(g, 3) == round(0.1607, 3)
    assert round(b, 3) == round(0.2313, 3)
    
    # Test fallback con valores inválidos
    assert service.hex_to_rgb("invalid") == (0.12, 0.23, 0.35)
    assert service.hex_to_rgb("") == (0.12, 0.23, 0.35)

def test_validation_invalid_hex():
    service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
    
    # Intentar guardar un color principal inválido
    with pytest.raises(ValueError, match="El campo primary_color debe ser un color hexadecimal"):
        service.save_customization("default", {
            "primary_color": "invalid_color",
            "secondary_color": "#64748B"
        })

@pytest.mark.asyncio
async def test_customization_persistence_and_api(client):
    # Asegurar inquilino default activo en el contexto
    tenant_context.set("default")
    
    # 1. Limpiar base de datos
    with _get_connection() as conn:
        conn.execute("DELETE FROM document_customization")
        conn.commit()

    # 2. Enviar actualización por API
    payload = {
        "logo_base64": MOCK_LOGO_BASE64,
        "primary_color": "#FF5733",
        "secondary_color": "#33FF57",
        "font_family": "Courier",
        "layout_template": "modern"
    }
    
    response = client.post("/api/v1/billing/customization", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # 3. Recuperar vía API y verificar
    response_get = client.get("/api/v1/billing/customization")
    assert response_get.status_code == 200
    data = response_get.json()
    assert data["logo_base64"] == MOCK_LOGO_BASE64
    assert data["primary_color"] == "#FF5733"
    assert data["secondary_color"] == "#33FF57"
    assert data["font_family"] == "Courier"
    assert data["layout_template"] == "modern"

@pytest.mark.asyncio
async def test_pdf_generation_with_customization():
    tenant_context.set("default")
    
    # Configurar diseño moderno y logo
    service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
    service.save_customization("default", {
        "logo_base64": MOCK_LOGO_BASE64,
        "primary_color": "#FF5733",
        "secondary_color": "#33FF57",
        "font_family": "Courier",
        "layout_template": "modern"
    })
    
    # Generar factura PDF
    res = await generate_invoice_pdf(
        client_name="Cliente Personalización Test",
        client_nif="12345678Z",
        amount=500.0,
        concept="Servicios de branding y diseño a medida",
        iva_rate=21.0,
        irpf_rate=15.0,
        confirmed_by_user=False # Se genera como Borrador de forma segura
    )
    
    assert res["status"] == "ok"
    pdf_path = res["pdf_path"]
    assert os.path.exists(pdf_path) is True
    
    # Eliminar PDF de prueba
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
