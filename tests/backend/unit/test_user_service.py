"""
Tests unitarios — UserService.
Sigue metodología TDD: primero los casos de fallo, luego los casos de éxito.
"""
import pytest
from app.domain.services.user_service import UserService


@pytest.fixture(autouse=True)
def limpiar_usuario():
    """Elimina el usuario antes de cada test para garantizar aislamiento."""
    from app.adapters.memory.memory import _get_connection
    with _get_connection("default") as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()
    yield
    with _get_connection("default") as conn:
        conn.execute("DELETE FROM app_user")
        conn.execute("DELETE FROM refresh_tokens")
        conn.commit()


# ── user_exists ────────────────────────────────────────────────────────────────

def test_user_not_exists_initially():
    """Sin usuario registrado, user_exists devuelve False."""
    assert UserService.user_exists() is False


# ── setup_user ────────────────────────────────────────────────────────────────

def test_setup_user_creates_user():
    """setup_user crea el usuario y devuelve un id positivo."""
    user_id = UserService.setup_user("admin", "password123", email="test@example.com")
    assert isinstance(user_id, int)
    assert user_id > 0
    assert UserService.user_exists() is True


def test_setup_user_normaliza_username_a_minusculas():
    """El username se normaliza a minúsculas."""
    UserService.setup_user("Admin", "password123")
    user = UserService.get_user()
    assert user.username == "admin"


def test_setup_user_falla_si_ya_existe_usuario():
    """Solo se permite un usuario por licencia. Segundo intento lanza ValueError."""
    UserService.setup_user("admin", "password123")
    with pytest.raises(ValueError, match="Solo se permite un usuario"):
        UserService.setup_user("otro", "otropass123")


def test_setup_user_falla_con_username_corto():
    """Username de menos de 3 caracteres lanza ValueError."""
    with pytest.raises(ValueError, match="al menos 3 caracteres"):
        UserService.setup_user("ab", "password123")


def test_setup_user_falla_con_password_corta():
    """Contraseña de menos de 8 caracteres lanza ValueError."""
    with pytest.raises(ValueError, match="al menos 8 caracteres"):
        UserService.setup_user("admin", "corta")


def test_setup_user_hashea_password():
    """La contraseña almacenada debe ser un hash bcrypt, nunca el texto en claro."""
    from app.adapters.memory.memory import _get_connection
    UserService.setup_user("admin", "password123")
    with _get_connection() as conn:
        row = conn.execute("SELECT password_hash FROM app_user LIMIT 1").fetchone()
    assert row["password_hash"] != "password123"
    assert row["password_hash"].startswith("$2b$")


# ── authenticate ──────────────────────────────────────────────────────────────

def test_authenticate_ok():
    """Credenciales correctas devuelven AppUser con datos correctos."""
    UserService.setup_user("admin", "password123", email="test@test.com")
    user = UserService.authenticate("admin", "password123")
    assert user is not None
    assert user.username == "admin"
    assert user.email == "test@test.com"


def test_authenticate_wrong_password():
    """Contraseña incorrecta devuelve None."""
    UserService.setup_user("admin", "password123")
    result = UserService.authenticate("admin", "wrongpassword")
    assert result is None


def test_authenticate_wrong_username():
    """Username inexistente devuelve None."""
    UserService.setup_user("admin", "password123")
    result = UserService.authenticate("noexiste", "password123")
    assert result is None


def test_authenticate_actualiza_last_login_at():
    """Un login exitoso actualiza el campo last_login_at."""
    UserService.setup_user("admin", "password123")
    user_before = UserService.get_user()
    assert user_before.last_login_at is None

    UserService.authenticate("admin", "password123")
    user_after = UserService.get_user()
    assert user_after.last_login_at is not None


# ── get_user ──────────────────────────────────────────────────────────────────

def test_get_user_sin_usuario_devuelve_none():
    """Si no hay usuario, get_user devuelve None."""
    assert UserService.get_user() is None


def test_get_user_devuelve_usuario_registrado():
    """Tras setup_user, get_user devuelve el AppUser correcto."""
    UserService.setup_user("admin", "password123", email="x@y.com")
    user = UserService.get_user()
    assert user is not None
    assert user.username == "admin"
    assert user.email == "x@y.com"
    assert user.is_active is True


# ── change_password ───────────────────────────────────────────────────────────

def test_change_password_ok():
    """Cambio de contraseña con la antigua correcta devuelve True."""
    UserService.setup_user("admin", "password123")
    result = UserService.change_password("password123", "newsecure456")
    assert result is True
    # Verificar que el nuevo password funciona
    user = UserService.authenticate("admin", "newsecure456")
    assert user is not None


def test_change_password_falla_con_wrong_old_password():
    """Contraseña antigua incorrecta devuelve False sin cambiar nada."""
    UserService.setup_user("admin", "password123")
    result = UserService.change_password("incorrecta", "newsecure456")
    assert result is False
    # El password original sigue funcionando
    user = UserService.authenticate("admin", "password123")
    assert user is not None


def test_change_password_falla_con_password_corta():
    """Nueva contraseña de menos de 8 caracteres lanza ValueError."""
    UserService.setup_user("admin", "password123")
    with pytest.raises(ValueError, match="al menos 8 caracteres"):
        UserService.change_password("password123", "corta")
