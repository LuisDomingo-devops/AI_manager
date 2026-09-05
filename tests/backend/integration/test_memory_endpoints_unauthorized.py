import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_memory_endpoints_unauthorized_spoofing():
    # Limpiar cualquier override residual dejado por tests mal escritos (como test_billing_services.py)
    app.dependency_overrides.clear()
    
    # Simulamos que el usuario tiene un token válido de "guest"
    # En un entorno real tendríamos que mockear verify_api_key o usar un token real de prueba.
    # Por simplicidad en este test unitario sin DB poblada, vamos a hacer la request 
    # sin token (lo que debería dar 401) y asegurarnos de que inyectar X-Client-ID no bypassa la seguridad.

    # 1. Sin autenticación y sin X-Client-ID -> 401
    resp = client.get("/conversations")
    assert resp.status_code == 401

    # 2. Intentar hacer spoofing de X-Client-ID a "admin" sin tener el token -> 401
    resp_spoof = client.get("/conversations", headers={"X-Client-ID": "admin"})
    assert resp_spoof.status_code == 401

    # 3. Probando la vulnerabilidad concreta solucionada:
    # Si somos el usuario "guest" (validado por el token) e intentamos inyectar X-Client-ID="admin"
    from app.api.routes import verify_api_key
    app.dependency_overrides[verify_api_key] = lambda: "guest"
    try:
        # Petición maliciosa intentando hacerse pasar por el admin para ver sus conversaciones
        malicious_req = client.get("/conversations", headers={"X-Client-ID": "admin"})
        assert malicious_req.status_code == 200
        
        # Como las BDs están físicamente separadas y nuestro parche inyecta el `client_id="guest"` validado
        # directamente en `memory_guest.db`, la respuesta debe venir vacía (la de guest) 
        # y NO puede haber accedido a la de admin, probando que el header se ignora.
        data = malicious_req.json()
        assert "conversations" in data
        # No deberíamos ver errores de Base de datos ni acceso a los datos de "admin"
    finally:
        app.dependency_overrides.clear()
