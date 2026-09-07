"""
Tests de integración — Endpoints de autenticación (/api/v1/auth/*).
Cubre el flujo completo: setup → login → me → refresh → logout.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.user_service import UserService
from app.config import settings


@pytest.fixture(autouse=True)
def limpiar_usuario():
    """Limpia usuario y tokens antes/después de cada test."""
    from app.adapters.memory.memory import _get_connection
    with _get_connection() as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def api_headers():
    return {"X-API-Key": settings.ALFONSO_API_KEY}


# ── /auth/setup ───────────────────────────────────────────────────────────────

def test_setup_crea_usuario(client, api_headers):
    """POST /auth/setup crea el usuario y devuelve 201."""
    resp = client.post("/api/v1/auth/setup", json={
        "username": "testuser",
        "password": "securepass",
        "email": "test@test.com"
    }, headers=api_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "testuser"
    assert "user_id" in data


def test_setup_requiere_api_key(client):
    """POST /auth/setup sin API Key devuelve 401."""
    resp = client.post("/api/v1/auth/setup", json={
        "username": "testuser",
        "password": "securepass"
    })
    assert resp.status_code == 401


def test_setup_falla_si_usuario_ya_existe(client, api_headers):
    """Segundo POST /auth/setup devuelve 409 Conflict."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)
    resp = client.post("/api/v1/auth/setup", json={
        "username": "otro", "password": "otrapass123"
    }, headers=api_headers)
    assert resp.status_code == 409


# ── /auth/login ───────────────────────────────────────────────────────────────

def test_login_devuelve_tokens(client, api_headers):
    """POST /auth/login con credenciales correctas devuelve JWT."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)

    resp = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "securepass"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_falla_con_credenciales_incorrectas(client, api_headers):
    """POST /auth/login con contraseña errónea devuelve 401."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)

    resp = client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


# ── /auth/me ──────────────────────────────────────────────────────────────────

def test_me_devuelve_perfil_con_token_valido(client, api_headers):
    """GET /auth/me con Bearer token válido devuelve datos del usuario."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass", "email": "u@u.com"
    }, headers=api_headers)

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "securepass"
    })
    access_token = login_resp.json()["access_token"]

    resp = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {access_token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["email"] == "u@u.com"
    assert "license" in data


def test_me_falla_sin_token(client):
    """GET /auth/me sin Bearer token devuelve 401 o 403."""
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code in (401, 403)


def test_me_falla_con_token_invalido(client):
    """GET /auth/me con token manipulado devuelve 401."""
    resp = client.get("/api/v1/auth/me", headers={
        "Authorization": "Bearer tokeninvalido.abc.xyz"
    })
    assert resp.status_code == 401


# ── /auth/refresh ─────────────────────────────────────────────────────────────

def test_refresh_emite_nuevo_access_token(client, api_headers):
    """POST /auth/refresh con refresh token válido devuelve nuevo access_token."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "securepass"
    })
    refresh_token = login_resp.json()["refresh_token"]

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


# ── /auth/logout ──────────────────────────────────────────────────────────────

def test_logout_revoca_refresh_token(client, api_headers):
    """POST /auth/logout revoca el refresh token. Refresh posterior falla."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "securepass"
    })
    tokens = login_resp.json()

    logout_resp = client.post("/api/v1/auth/logout", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert logout_resp.status_code == 200

    # Refresh después de logout → 401
    refresh_resp = client.post("/api/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert refresh_resp.status_code == 401


# ── /auth/password ────────────────────────────────────────────────────────────

def test_cambiar_password_ok(client, api_headers):
    """PATCH /auth/password cambia la contraseña correctamente."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)

    login_resp = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "securepass"
    })
    access_token = login_resp.json()["access_token"]

    resp = client.patch("/api/v1/auth/password", json={
        "old_password": "securepass",
        "new_password": "nuevapassword456"
    }, headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200

    # El nuevo password funciona
    login2 = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "nuevapassword456"
    })
    assert login2.status_code == 200


def test_cambiar_password_falla_con_password_antigua_incorrecta(client, api_headers):
    """PATCH /auth/password con contraseña antigua incorrecta devuelve 401."""
    client.post("/api/v1/auth/setup", json={
        "username": "testuser", "password": "securepass"
    }, headers=api_headers)
    login_resp = client.post("/api/v1/auth/login", json={
        "username": "testuser", "password": "securepass"
    })
    access_token = login_resp.json()["access_token"]

    resp = client.patch("/api/v1/auth/password", json={
        "old_password": "incorrecta",
        "new_password": "nuevapassword456"
    }, headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 401
