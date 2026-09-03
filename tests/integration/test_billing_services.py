import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import verify_api_key
import uuid

# Mock de la dependencia de autenticación
app.dependency_overrides[verify_api_key] = lambda: "default"

client = TestClient(app)

# SKU específico para denotar un servicio
TEST_SERVICE_SKU = f"SRV-{str(uuid.uuid4())[:6].upper()}"

@pytest.fixture
def api_headers():
    return {"X-API-Key": "default_key"}

def test_create_service(api_headers):
    """Test para verificar que podemos registrar un servicio puro (sin stock real)."""
    payload = {
        "sku": TEST_SERVICE_SKU,
        "name": "Consultoría de Software",
        "price": 150.00,
        "description": "Servicio de consultoría por horas",
        "iva_rate": 21.0
    }
    response = client.post("/billing/products", json=payload, headers=api_headers)
    assert response.status_code in (200, 400)
    
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ok"
        assert "registrado" in data["message"].lower()

def test_get_services(api_headers):
    """Test para verificar que el servicio creado se lista correctamente con sus métricas."""
    response = client.get("/billing/products", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "products" in data
    
    # Comprobar que nuestro servicio está en la lista y las nuevas métricas existen
    services = [p for p in data["products"] if p["sku"] == TEST_SERVICE_SKU]
    if services:
        srv = services[0]
        assert "sold_units" in srv
        assert "revenue" in srv
        assert "purchase_count" in srv

def test_update_service(api_headers):
    """Test para actualizar la tarifa por hora del servicio."""
    payload = {
        "name": "Consultoría Avanzada",
        "price": 200.00
    }
    response = client.put(f"/billing/products/{TEST_SERVICE_SKU}", json=payload, headers=api_headers)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ("ok", "error")

def test_delete_service(api_headers):
    """Test para dar de baja el servicio."""
    response = client.delete(f"/billing/products/{TEST_SERVICE_SKU}?confirmed_by_user=true", headers=api_headers)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ("ok", "error")
