"""
Tests de Integración para los Endpoints de Callback Público y Autorización Bancaria.
Verifica que las peticiones web no requieran cabeceras de API Key y devuelvan HTML válido (sin errores JSON 401/404).
"""
import io
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.bank_service import BankService

@pytest.fixture
def unauthenticated_client():
    # Cliente sin ninguna cabecera de autenticación X-API-Key ni X-Session-Token
    return TestClient(app)

@pytest.fixture
def authenticated_client():
    headers = {"X-API-Key": "test_api_key_default"}
    with TestClient(app) as c:
        c.headers.update(headers)
        yield c


def test_public_callback_endpoint_success(unauthenticated_client):
    # Simula la redirección tras autorización exitosa
    response = unauthenticated_client.get("/callback?bank=Wise&ref=alfonso_test_123")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "¡Conexión Bancaria Exitosa!" in response.text
    assert "Wise" in response.text


def test_public_callback_endpoint_error(unauthenticated_client):
    # Simula el retorno cuando el usuario cancela en la pasarela bancaria
    response = unauthenticated_client.get("/callback?error=access_denied&details=El_usuario_cancelo_el_consentimiento")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Error en la Autorización Bancaria" in response.text
    assert "access_denied" in response.text


def test_public_mock_auth_endpoint(unauthenticated_client):
    # Simula la apertura del enlace de autorización en el navegador web
    response = unauthenticated_client.get("/bank/mock-auth?redirect=http://localhost:8000/callback&bank=Santander")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Conectar Alfonso con Santander" in response.text
    assert "http://localhost:8000/callback" in response.text


def test_import_bank_statement_endpoint_wise_csv(authenticated_client):
    csv_content = b"""TransferWise ID,Date,Amount,Currency,Description,Payment Reference
WISE-991,2026-08-15,750.00,EUR,Cobro Factura Cliente Wise,FAC-991
WISE-992,2026-08-16,-30.00,EUR,Gasto Comision Pasarela,FEE-01
"""
    files = {"file": ("extracto_wise.csv", io.BytesIO(csv_content), "text/csv")}
    response = authenticated_client.post("/tax/bank/import", files=files)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["imported_count"] == 2
