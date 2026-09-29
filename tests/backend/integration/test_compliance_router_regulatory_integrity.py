import pytest
from starlette.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)

def test_compliance_router_declaration_endpoint_returns_unverified_draft():
    """
    Verifica que la API pública de compliance no emita declaraciones 'ok' definitivas
    y exponga fielmente status='draft' y regulatory_status='UNVERIFIED'.
    """
    response = client.get(
        "/api/v1/compliance/declaration",
        headers={"X-API-Key": settings.ALFONSO_API_KEY}
    )
    assert response.status_code == 200, f"Error al consultar endpoint: {response.text}"
    data = response.json()

    assert data["status"] == "ok", f"La API debe devolver respuesta exitosa 'ok', recibido: {data.get('status')}"
    assert data.get("declaration_state") == "draft", f"La API debe exponer declaration_state='draft', recibido: {data.get('declaration_state')}"
    assert data.get("regulatory_status") == "UNVERIFIED", (
        f"La API debe exponer regulatory_status='UNVERIFIED', recibido: {data.get('regulatory_status')}"
    )
    assert "cumple íntegramente" not in data.get("statement", "").lower(), (
        "El statement no debe afirmar cumplimiento íntegro en la API"
    )
