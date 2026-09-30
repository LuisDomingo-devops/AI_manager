import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.adapters.memory.memory import memory
import os

def test_leak():
    from app.infrastructure.database.connection_manager import tenant_context
    from app.api.routes import verify_api_key
    tenant_context.set("default")
    
    app.dependency_overrides.clear()
    try:
        memory.add_message("leak_session", "user", "secret_data", client_id="victim")
        
        with TestClient(app) as client:
            r1 = client.get("/memory/leak_session", headers={"X-API-Key": ""})
            assert r1.status_code == 401, f"No auth should be 401, got {r1.status_code}"
            
            # Try with attacker token
            from app.infrastructure.security.session_manager import SessionManager
            attacker_token = SessionManager.create_session("attacker")
            r2 = client.get("/memory/leak_session", headers={"X-Session-Token": attacker_token, "X-API-Key": ""})
            assert r2.status_code == 200
            
            # Did it leak?
            data = r2.json()
            assert len(data.get("messages", [])) == 0, f"Leaked! {data}"
    finally:
        app.dependency_overrides[verify_api_key] = lambda: "test_api_key_default"
