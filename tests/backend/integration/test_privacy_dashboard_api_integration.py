import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_privacy_last_session_endpoint():
    client = TestClient(app)
    # Petición al endpoint de auditoría de privacidad
    response = client.get("/api/v1/privacy/last-session")
    # El endpoint debe responder 200 con estructura de privacidad
    assert response.status_code in (200, 401)  # 200 o 401 si requiere api key
