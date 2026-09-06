import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.adapters.memory.memory import memory
import os

def test_leak():
    from app.infrastructure.database.connection_manager import tenant_context
    tenant_context.set("default")
    
    memory.add_message("leak_session", "user", "secret_data", client_id="victim")
    
    with TestClient(app) as client:
        # Try without auth
        r1 = client.get("/memory/leak_session")
        assert r1.status_code == 401, f"No auth should be 401, got {r1.status_code}"
        
        # Try with attacker token
        from app.infrastructure.security.session_manager import SessionManager
        attacker_token = SessionManager.create_session("attacker")
        r2 = client.get("/memory/leak_session", headers={"X-Session-Token": attacker_token})
        assert r2.status_code == 200
        
        # Did it leak?
        data = r2.json()
        assert len(data.get("messages", [])) == 0, f"Leaked! {data}"
        print("No leak detected!")
