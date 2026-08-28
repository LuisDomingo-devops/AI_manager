import pytest
import json
import os
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.document_customization_service import DocumentCustomizationService
from app.adapters.document_customization import SqliteDocumentCustomizationAdapter
from app.adapters.memory.memory import _get_connection, tenant_context
from app.tools.server.billing_tools import generate_invoice_pdf, create_quote

# Logo mínimo en base64 de prueba
MOCK_LOGO_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)

@pytest.fixture(scope="module")
def client():
    headers = {"X-API-Key": "test_api_key_default"}
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c

@pytest.mark.asyncio
async def test_customization_layout_persistence_via_api(client):
    """Verifica que el layout de elementos de la maquetación se persista correctamente a través de los endpoints de la API."""
    tenant_context.set("default")
    
    # 1. Limpiar base de datos
    with _get_connection() as conn:
        conn.execute("DELETE FROM document_customization")
        conn.commit()

    # 2. Enviar actualización con layouts y ancho del logo por API
    custom_order = ["cabecera", "detalles", "totales", "emisor_receptor", "pie_verifactu"]
    custom_quote_order = ["pie_verifactu", "totales", "detalles", "emisor_receptor", "cabecera"]
    payload = {
        "logo_base64": MOCK_LOGO_BASE64,
        "primary_color": "#002244",
        "secondary_color": "#556677",
        "font_family": "Courier",
        "layout_template": "minimalist",
        "elements_layout": json.dumps(custom_order),
        "quote_elements_layout": json.dumps(custom_quote_order),
        "logo_width": 140
    }
    
    response = client.post("/api/v1/billing/customization", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    # 3. Recuperar vía API y verificar el orden guardado
    response_get = client.get("/api/v1/billing/customization")
    assert response_get.status_code == 200
    data = response_get.json()
    assert data["logo_base64"] == MOCK_LOGO_BASE64
    assert data["primary_color"] == "#002244"
    assert data["secondary_color"] == "#556677"
    assert data["font_family"] == "Courier"
    assert data["layout_template"] == "minimalist"
    assert data["logo_width"] == 140
    
    saved_layout = json.loads(data["elements_layout"])
    assert saved_layout == custom_order
    saved_quote_layout = json.loads(data["quote_elements_layout"])
    assert saved_quote_layout == custom_quote_order

@pytest.mark.asyncio
async def test_invoice_pdf_generation_with_custom_layout():
    """Verifica que la generación de facturas PDF se complete con éxito usando un orden de elementos personalizado en ReportLab."""
    tenant_context.set("default")
    
    # Configurar maquetación de test con orden alterado
    service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
    custom_order = ["pie_verifactu", "totales", "detalles", "emisor_receptor", "cabecera"]
    service.save_customization("default", {
        "logo_base64": MOCK_LOGO_BASE64,
        "primary_color": "#123456",
        "secondary_color": "#654321",
        "font_family": "Helvetica",
        "layout_template": "modern",
        "elements_layout": json.dumps(custom_order)
    })
    
    # Generar factura PDF
    res = await generate_invoice_pdf(
        client_name="Cliente Integracion Maquetacion",
        client_nif="12345678Z",
        amount=150.0,
        concept="Prueba de integración de reordenación de PDF",
        iva_rate=21.0,
        irpf_rate=15.0,
        confirmed_by_user=False  # Genera borrador
    )
    
    assert res["status"] == "ok"
    pdf_path = res["pdf_path"]
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    
    # Limpiar PDF generado
    try:
        os.remove(pdf_path)
    except Exception:
        pass


@pytest.mark.asyncio
async def test_quote_pdf_generation_with_custom_layout():
    """Verifica que la generación de presupuestos en PDF se complete con éxito usando un orden de elementos personalizado en ReportLab."""
    tenant_context.set("default")
    
    # Configurar maquetación de test con orden alterado
    service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())
    custom_order = ["pie_verifactu", "totales", "detalles", "emisor_receptor", "cabecera"]
    service.save_customization("default", {
        "logo_base64": MOCK_LOGO_BASE64,
        "primary_color": "#123456",
        "secondary_color": "#654321",
        "font_family": "Helvetica",
        "layout_template": "modern",
        "elements_layout": json.dumps(custom_order)
    })
    
    # Generar presupuesto PDF (create_quote es síncrono y devuelve un diccionario)
    res = create_quote(
        client_name="Cliente Integracion Presupuesto Maquetacion",
        client_nif="12345678Z",
        amount=350.0,
        concept="Prueba de integración de reordenación de presupuesto PDF",
        iva_rate=21.0,
        irpf_rate=15.0,
        is_draft=True
    )
    
    assert res is not None
    assert "file_path" in res
    pdf_path = res["file_path"]
    assert pdf_path is not None
    assert os.path.exists(pdf_path)
    
    # Limpiar PDF generado
    try:
        os.remove(pdf_path)
    except Exception:
        pass
