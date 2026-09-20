import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_auth_setup_requires_auth(monkeypatch):
    # Mock user exists
    from app.domain.services.user_service import UserService
    monkeypatch.setattr(UserService, "user_exists", lambda: True)
    
    # Without token
    response = client.post("/api/v1/auth/setup", json={"username": "test", "password": "password"})
    assert response.status_code in (401, 403, 409)
