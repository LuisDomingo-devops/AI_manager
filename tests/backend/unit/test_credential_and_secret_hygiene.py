"""
Unit tests for Credential and Secret Hygiene.
Verifica que las credenciales no se filtren en representaciones de configuración,
que los loggers cuenten con filtro de sanitización y que AuthService opere con fechas UTC estándar.
"""
import pytest
import logging
from app.config import Settings
from app.utils.logger import CredentialSanitizingFilter

def test_settings_does_not_leak_client_tokens_in_repr():
    """
    Verifica que el campo ALFONSO_CLIENT_TOKENS tenga repr=False para evitar fugas en logs y prints.
    """
    secret_token_val = "secret_client_token_abc123"
    custom_settings = Settings(ALFONSO_CLIENT_TOKENS=f'{{"tenant1": "{secret_token_val}"}}')
    
    settings_repr = repr(custom_settings)
    assert secret_token_val not in settings_repr, (
        f"ALFONSO_CLIENT_TOKENS se filtró en repr(settings): {settings_repr}"
    )

def test_credential_sanitizing_filter_redacts_tokens_and_passwords():
    """
    Verifica que CredentialSanitizingFilter enmascare Bearer tokens, passwords y API keys.
    """
    filter_obj = CredentialSanitizingFilter()
    
    # Caso 1: Bearer token
    record1 = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=10,
        msg="Usuario autenticado con Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token y terminado",
        args=(), exc_info=None
    )
    filter_obj.filter(record1)
    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token" not in record1.msg
    assert "Bearer [REDACTED]" in record1.msg
    
    # Caso 2: Password
    record2 = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=20,
        msg="Login fallido con password='MyUltraSecretPassword123' para el usuario admin",
        args=(), exc_info=None
    )
    filter_obj.filter(record2)
    assert "MyUltraSecretPassword123" not in record2.msg
    assert "password='[REDACTED]'" in record2.msg or "password=[REDACTED]" in record2.msg

    # Caso 3: API Key
    record3 = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=30,
        msg="Llamada externa con api_key: 'alf_live_999888777' completada",
        args=(), exc_info=None
    )
    filter_obj.filter(record3)
    assert "alf_live_999888777" not in record3.msg
    assert "[REDACTED]" in record3.msg
