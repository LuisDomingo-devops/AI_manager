"""Pruebas unitarias para validación de esquemas OpenAPI locales (T036 - TDD).

Valida que la aplicación FastAPI exponga esquemas OpenAPI versionados y conformes
con los contratos formales para GUI PyQt6 y extensiones de navegador.
"""

from fastapi.testclient import TestClient
from app.main import app


def test_openapi_schema_contains_required_contract_endpoints():
    client = TestClient(app)
    response = client.get("/openapi.json")
    
    assert response.status_code == 200
    schema = response.json()
    
    assert "openapi" in schema
    assert "paths" in schema
    paths = schema["paths"]
    
    # Comprobar rutas contractuales clave
    assert "/api/v1/billing/invoices/legal/issue" in paths
    assert "/api/v1/billing/invoices" in paths
    
    # Comprobar esquemas de datos expuestos
    components = schema.get("components", {}).get("schemas", {})
    assert "InvoiceCreateRequest" in components
