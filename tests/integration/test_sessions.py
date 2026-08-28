import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

@pytest.fixture(autouse=True)
def setup_test_env():
    os.environ["TESTING"] = "true"
    # Asegurar que use la API Key configurada para test
    settings.ALFONSO_API_KEY = "test_api_key_default"
    
    # Limpiar tabla de sesiones
    from app.adapters.memory.memory import _get_connection
    from app.infrastructure.security.session_manager import SessionManager
    SessionManager._db_initialized = False
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS user_sessions")
        conn.commit()

def test_session_auth_flow():
    client = TestClient(app)
    
    # 1. Intentar acceder a un endpoint protegido sin credenciales -> 401
    resp = client.get("/memory")
    assert resp.status_code == 401
    
    # 2. Intentar login con API Key incorrecta -> 401
    resp = client.post("/auth/login", json={"client_id": "client_a"}, headers={"X-API-Key": "wrong_key"})
    assert resp.status_code == 401
    
    # 3. Login correcto -> 200 y devuelve session_token
    resp = client.post("/auth/login", json={"client_id": "client_a"}, headers={"X-API-Key": "test_api_key_default"})
    assert resp.status_code == 200
    body = resp.json()
    assert "session_token" in body
    assert body["client_id"] == "client_a"
    session_token = body["session_token"]
    
    # 4. Acceder al endpoint protegido usando el X-Session-Token -> 200
    resp_protected = client.get("/memory", headers={"X-Session-Token": session_token})
    assert resp_protected.status_code == 200
    
    # 5. Hacer logout con el token de sesión -> 200
    resp_logout = client.post("/auth/logout", headers={"X-Session-Token": session_token})
    assert resp_logout.status_code == 200
    
    # 6. Intentar acceder de nuevo tras logout -> 401
    resp_post_logout = client.get("/memory", headers={"X-Session-Token": session_token})
    assert resp_post_logout.status_code == 401
