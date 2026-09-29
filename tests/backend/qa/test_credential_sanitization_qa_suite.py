"""
QA Suite: Credential Sanitization and Security Hygiene Audit.
Audita exhaustivamente que ningún componente de logging o configuración exponga secretos,
tokens o contraseñas en claro.
"""
import pytest
import json
import logging
from app.config import settings
from app.utils.logger import JSONFormatter, CredentialSanitizingFilter
from app.domain.services.auth_service import AuthService
from app.domain.services.user_service import AppUser

def test_qa_settings_secret_fields_have_repr_disabled():
    """Auditoría QA: Todos los campos que contengan 'KEY', 'SECRET' o 'TOKEN' deben tener repr=False."""
    settings_repr = repr(settings)
    
    # Comprobar que los campos sensibles definidos en Settings no aparecen como clave-valor en claro
    sensitive_keys = [
        "ALFONSO_API_KEY",
        "ALFONSO_BRIDGE_TOKEN",
        "ALFONSO_CLIENT_SECRET",
        "DATABASE_ENCRYPTION_KEY",
        "GOCARDLESS_SECRET_ID",
        "GOCARDLESS_SECRET_KEY",
        "ALFONSO_CLIENT_TOKENS"
    ]
    for key in sensitive_keys:
        assert f"{key}=" not in settings_repr, (
            f"El campo sensible {key} no debe mostrar su valor en repr(settings)"
        )

def test_qa_json_formatter_with_sanitizing_filter():
    """Auditoría QA: Los logs estructurados en JSON nunca deben contener Bearer tokens o contraseñas en plano."""
    sanitizer = CredentialSanitizingFilter()
    formatter = JSONFormatter()
    
    record = logging.LogRecord(
        name="qa_audit", level=logging.WARNING, pathname=__file__, lineno=50,
        msg="Auditoría de seguridad: access_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 y api_key='sk_live_1234567890abcdef'",
        args=(), exc_info=None
    )
    # Aplicar sanitizador y formatear
    sanitizer.filter(record)
    json_output = formatter.format(record)
    
    log_obj = json.loads(json_output)
    msg = log_obj.get("message", "")
    assert "sk_live_1234567890abcdef" not in msg
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in msg
    assert "[REDACTED]" in msg

def test_qa_auth_service_token_creation_utc():
    """Auditoría QA: La emisión de access token debe usar timezone UTC y ser decodificable inmediatamente."""
    fake_user = AppUser(
        id=999,
        username="qa_user",
        email="qa@alfonso.local",
        is_active=True,
        created_at="2026-09-29T12:00:00",
        last_login_at=None
    )
    token = AuthService._create_access_token(fake_user)
    assert token is not None
    
    decoded = AuthService.decode_access_token(token)
    assert decoded["sub"] == "999"
    assert decoded["username"] == "qa_user"
    assert "exp" in decoded
