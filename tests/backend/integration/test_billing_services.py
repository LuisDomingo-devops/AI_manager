"""
Tests de Integración de Servicios de Facturación (Spec 005 - US2).
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
        conn.execute("DELETE FROM products WHERE sku LIKE 'SRV-%'")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM products WHERE sku LIKE 'SRV-%'")
        conn.commit()
    tenant_context.reset(token)

@pytest.fixture
def api_headers():
    return {"X-API-Key": "test_api_key_default", "X-Client-ID": "default"}


def test_create_service(api_headers):
    """Verifica que podemos registrar un servicio puro (item_type='service') con HTTP 200 OK."""
    sku = f"SRV-{uuid.uuid4().hex[:6].upper()}"
    payload = {
        "sku": sku,
        "name": "Consultoría de Software",
        "price": 150.00,
        "description": "Servicio de consultoría por horas",
        "iva_rate": 21.0,
        "item_type": "service"
    }
    response = client.post("/billing/products", json=payload, headers=api_headers)
    assert response.status_code == 200, f"Error al crear servicio: {response.text}"
    
    data = response.json()
    assert data["status"] == "ok"
    assert "registrado" in data["message"].lower()


def test_get_services(api_headers):
    """Verifica que el servicio creado se lista correctamente con sus métricas."""
    sku = f"SRV-{uuid.uuid4().hex[:6].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Consultoría de Software",
        "price": 150.00,
        "description": "Servicio de consultoría por horas",
        "iva_rate": 21.0,
        "item_type": "service"
    }
    create_res = client.post("/billing/products", json=create_payload, headers=api_headers)
    assert create_res.status_code == 200, f"Fallo en create_service: {create_res.text}"

    response = client.get("/billing/products", headers=api_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "products" in data
    
    services = [p for p in data["products"] if p["sku"] == sku]
    assert len(services) == 1
    srv = services[0]
    assert "sold_units" in srv
    assert "revenue" in srv
    assert "purchase_count" in srv


def test_update_service(api_headers):
    """Verifica la actualización de la tarifa por hora del servicio con HTTP 200 OK."""
    sku = f"SRV-{uuid.uuid4().hex[:6].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Consultoría Base",
        "price": 100.00,
        "description": "Base",
        "iva_rate": 21.0,
        "item_type": "service"
    }
    create_res = client.post("/billing/products", json=create_payload, headers=api_headers)
    assert create_res.status_code == 200, f"Fallo en create_service: {create_res.text}"

    payload = {
        "name": "Consultoría Avanzada",
        "price": 200.00
    }
    response = client.put(f"/billing/products/{sku}", json=payload, headers=api_headers)
    assert response.status_code == 200, f"Error al actualizar servicio: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert "actualizado" in data["message"].lower()


def test_delete_service(api_headers):
    """Verifica la baja estricta del servicio con HTTP 200 OK."""
    sku = f"SRV-{uuid.uuid4().hex[:6].upper()}"
    create_payload = {
        "sku": sku,
        "name": "Consultoría Para Eliminar",
        "price": 120.00,
        "description": "Para baja",
        "iva_rate": 21.0,
        "item_type": "service"
    }
    create_res = client.post("/billing/products", json=create_payload, headers=api_headers)
    assert create_res.status_code == 200, f"Fallo en create_service: {create_res.text}"

    response = client.delete(f"/billing/products/{sku}", headers=api_headers)
    assert response.status_code == 200, f"Error al eliminar servicio: {response.text}"
    data = response.json()
    assert data["status"] == "ok"
    assert "eliminado" in data["message"].lower()
