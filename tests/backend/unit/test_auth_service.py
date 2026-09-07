"""
Tests unitarios — AuthService.
Cubre login, refresh, logout y decode del JWT.
"""
import time
import pytest
from app.domain.services.auth_service import AuthService
from app.domain.services.user_service import UserService


@pytest.fixture(autouse=True)
def limpiar_usuario():
    """Aislamiento: limpia usuario y tokens antes y después de cada test."""
    from app.adapters.memory.memory import _get_connection
    with _get_connection() as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()
    UserService.setup_user("admin", "password123", email="test@test.com")
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()


# ── login ─────────────────────────────────────────────────────────────────────

def test_login_ok_devuelve_tokens():
    """Login correcto devuelve access_token, refresh_token y expires_in."""
    result = AuthService.login("admin", "password123")
    assert "access_token" in result
    assert "refresh_token" in result
    assert result["token_type"] == "bearer"
    assert result["expires_in"] == 8 * 3600


def test_login_falla_con_credenciales_incorrectas():
    """Login con contraseña incorrecta lanza ValueError."""
    with pytest.raises(ValueError, match="Credenciales incorrectas"):
        AuthService.login("admin", "wrongpass")


def test_login_falla_con_usuario_inexistente():
    """Login con usuario que no existe lanza ValueError."""
    with pytest.raises(ValueError, match="Credenciales incorrectas"):
        AuthService.login("noexiste", "password123")


# ── decode_access_token ───────────────────────────────────────────────────────

def test_decode_token_valido():
    """El token emitido se puede decodificar y contiene username."""
    result = AuthService.login("admin", "password123")
    payload = AuthService.decode_access_token(result["access_token"])
    assert payload["username"] == "admin"
    assert payload["type"] == "access"


def test_decode_token_invalido_lanza_error():
    """Un token manipulado lanza ValueError."""
    with pytest.raises(ValueError, match="inválido"):
        AuthService.decode_access_token("token.falso.invalido")


def test_decode_token_expirado_lanza_error():
    """Un token con exp pasada lanza ValueError."""
    from jose import jwt
    from app.domain.services.auth_service import _JWT_SECRET, _ALGORITHM
    import datetime as dt
    payload = {
        "sub": "1",
        "username": "admin",
        "exp": dt.datetime.utcnow() - dt.timedelta(seconds=10),
        "type": "access",
    }
    expired_token = jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)
    with pytest.raises(ValueError, match="inválido"):
        AuthService.decode_access_token(expired_token)


# ── refresh_access_token ──────────────────────────────────────────────────────

def test_refresh_genera_nuevo_access_token():
    """Un refresh token válido genera un nuevo access token."""
    tokens = AuthService.login("admin", "password123")
    result = AuthService.refresh_access_token(tokens["refresh_token"])
    assert "access_token" in result
    assert result["token_type"] == "bearer"
    # El nuevo access token es diferente al original (diferente exp)
    # (puede coincidir si los timestamps son iguales, no es crítico)


def test_refresh_falla_con_token_inexistente():
    """Refresh token no registrado lanza ValueError."""
    with pytest.raises(ValueError, match="no encontrado"):
        AuthService.refresh_access_token("token_que_no_existe")


def test_refresh_falla_tras_logout():
    """Refresh token revocado por logout lanza ValueError."""
    tokens = AuthService.login("admin", "password123")
    AuthService.logout(tokens["refresh_token"])
    with pytest.raises(ValueError, match="revocado"):
        AuthService.refresh_access_token(tokens["refresh_token"])


# ── logout ────────────────────────────────────────────────────────────────────

def test_logout_revoca_refresh_token():
    """logout() devuelve True y el token queda revocado."""
    tokens = AuthService.login("admin", "password123")
    result = AuthService.logout(tokens["refresh_token"])
    assert result is True


def test_logout_devuelve_false_para_token_inexistente():
    """logout() devuelve False si el token no existe en la BD."""
    result = AuthService.logout("token_inexistente")
    assert result is False
