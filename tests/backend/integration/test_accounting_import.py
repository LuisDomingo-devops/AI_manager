import pytest
import json
from fastapi.testclient import TestClient
from app.main import app
from app.api.auth_deps import get_current_user
from app.domain.services.user_service import AppUser

client = TestClient(app)

def mock_get_current_user():
    return AppUser(id=1, username="test_user", email="test@example.com", is_active=True, created_at="", last_login_at="")

@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[get_current_user] = mock_get_current_user
    yield
    app.dependency_overrides.clear()
@pytest.mark.skip(reason="A3 parser removed in Phase 5")
def test_import_a3_success():
    headers = {}
    a3_content = b"0101012023        12345678X PROVEEDOR A3                          0000001000000000210"
    
    files = {"file": ("SUENLACE.DAT", a3_content, "text/plain")}
    data = {"source_type": "A3"}
    
    response = client.post("/api/v1/import/accounting", headers=headers, files=files, data=data)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_import_generic_csv_success():
    headers = {}
    csv_content = b"Fecha,Base Imponible,IVA\n2023-01-01,100.0,21.0"
    
    mapping = {
        "date": "Fecha",
        "base": "Base Imponible",
        "iva_amount": "IVA"
    }
    
    files = {"file": ("facturas.csv", csv_content, "text/csv")}
    data = {
        "source_type": "GENERIC_CSV",
        "mapping_config": json.dumps(mapping)
    }
    
    response = client.post("/api/v1/import/accounting", headers=headers, files=files, data=data)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["imported"] == 1
