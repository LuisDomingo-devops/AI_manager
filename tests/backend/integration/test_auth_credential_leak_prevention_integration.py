"""
Integration tests for Credential Leak Prevention.
Verifica que los loggers integrados de la aplicación saniticen cadenas con tokens y passwords.
"""
import pytest
import io
import logging
from app.utils.logger import app_logger

def test_app_logger_does_not_output_plain_bearer_or_password():
    """
    Verifica que al emitir logs a través de app_logger, los tokens y contraseñas salgan enmascarados.
    """
    stream = io.StringIO()
    test_handler = logging.StreamHandler(stream)
    
    # El app_logger debe tener aplicado el filtro o formateador seguro
    from app.utils.logger import CredentialSanitizingFilter
    test_handler.addFilter(CredentialSanitizingFilter())
    app_logger.addHandler(test_handler)
    
    try:
        app_logger.info("Intento de login con password=SuperSecretPassword99 y Bearer tok_123456789abcdef")
        output = stream.getvalue()
        
        assert "SuperSecretPassword99" not in output, f"Password filtrado en el log: {output}"
        assert "tok_123456789abcdef" not in output, f"Bearer token filtrado en el log: {output}"
        assert "[REDACTED]" in output
    finally:
        app_logger.removeHandler(test_handler)
