"""
Tests de Integración de Productos de Facturación (Spec 005 - US2).
Saneado conforme al Contrato de Discovery (Sección 5 y 7):
Elimina aserciones ambiguas 'in (200, 400)', garantiza SKUs independientes por prueba
y preserva la autenticación global sin romper app.dependency_overrides.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.adapters.memory.memory import _get_connection, tenant_context

pytestmark = pytest.mark.usefixtures("mock_approval_service")

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_default_tenant_and_cleanup():
    token = tenant_context.set("default")
    with _get_connection() as conn:
        conn.execute("DELETE FROM products WHERE sku LIKE 'TEST-%'")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM products WHERE sku LIKE 'TEST-%'")
        conn.commit()
    tenant_context.reset(token)

@pytest.fixture
def api_headers():
    return {"X-API-Key": "test_api_key_default", "X-Client-ID": "default"}


def test_create_product(api_headers):
    """Verifica la creación determinista de un producto con HTTP 200 OK."""
    sku = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    payload = {
        "sku": sku,
        "name": "Producto de Test",
        "price": 99.99,
        "description": "Descripción de prueba",
        "iva_rate": 21.0
    }
    response = client.post("/billing/products", json=payload, headers=api_headers)
    assert response.status_code == 200, f"Fallo al crear producto: {response.text}"
    
    data = response.json()
    assert data["status"] == "ok"
    assert "registrado" in data["message"].lower()


def test_get_products(api_headers):
    """Verifica que el listado de productos responde 200 y contiene la lista."""
    response = client.get("/billing/products", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "products" in data
    assert isinstance(data["products"], list)


def test_update_product(api_headers):
    """Verifica la actualización estricta de un producto existente con HTTP 200 OK."""
    sku = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Producto Previo",
        "price": 50.0,
        "description": "Para actualizar",
        "iva_rate": 21.0
    }
    create_res = client.post("/billing/products", json=create_payload, headers=api_headers)
    assert create_res.status_code == 200, f"Fallo en precondición create_product: {create_res.text}"

    update_payload = {
        "name": "Producto Actualizado",
        "price": 105.00
    }
    response = client.put(f"/billing/products/{sku}", json=update_payload, headers=api_headers)
    assert response.status_code == 200, f"Fallo al actualizar producto: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert "actualizado" in data["message"].lower()


def test_delete_product(api_headers):
    """Verifica el borrado estricto (Soft Delete) de un producto con HTTP 200 OK."""
    sku = f"TEST-{uuid.uuid4().hex[:8].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Producto Para Borrar",
        "price": 75.0,
        "description": "Para eliminar",
        "iva_rate": 21.0
    }
    create_res = client.post("/billing/products", json=create_payload, headers=api_headers)
    assert create_res.status_code == 200, f"Fallo en precondición create_product: {create_res.text}"

    response = client.delete(f"/billing/products/{sku}", headers=api_headers)
    assert response.status_code == 200, f"Fallo al borrar producto: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert "eliminado" in data["message"].lower()
