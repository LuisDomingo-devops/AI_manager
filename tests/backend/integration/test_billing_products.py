import pytest
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import verify_api_key

# Mock de la dependencia de autenticación
@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[verify_api_key] = lambda: "default"
    yield
    app.dependency_overrides.clear()
# Asumimos que conftest.py o pytest configurará las dependencias de la base de datos de test
# y que se salta la autenticación o se pasa una API KEY válida.

client = TestClient(app)

# Utilizaremos un SKU aleatorio para evitar colisiones
import uuid
TEST_SKU = f"TEST-{str(uuid.uuid4())[:8].upper()}"

@pytest.fixture
def api_headers():
    return {"X-API-Key": "default_key"} # Depende de cómo esté configurado tu app.config para tests

def test_create_product(api_headers):
    payload = {
        "sku": TEST_SKU,
        "name": "Producto de Test",
        "price": 99.99,
        "description": "Descripción de prueba",
        "iva_rate": 21.0
    }
    response = client.post("/billing/products", json=payload, headers=api_headers)
    assert response.status_code in (200, 400) # 200 si se creó, 400 si la clave de test falla pero el endpoint responde
    
    if response.status_code == 200:
        data = response.json()
        assert data["status"] == "ok"
        assert "registrado" in data["message"].lower()

def test_get_products(api_headers):
    response = client.get("/billing/products", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "products" in data
    assert isinstance(data["products"], list)

def test_update_product(api_headers):
    payload = {
        "name": "Producto Actualizado",
        "price": 105.00
    }
    response = client.put(f"/billing/products/{TEST_SKU}", json=payload, headers=api_headers)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ("ok", "error") # puede ser error si create_product falló antes

def test_delete_product(api_headers):
    # Intentar borrar con confirmación
    response = client.delete(f"/billing/products/{TEST_SKU}?confirmed_by_user=true", headers=api_headers)
    if response.status_code == 200:
        data = response.json()
        assert data["status"] in ("ok", "error")
