import os
import pytest
from unittest.mock import patch
import app.utils.encryption as enc


def test_encryption_key_fail_fast_in_production():
    """
    Verifica que en entorno de producción (ALFONSO_ENV=production),
    si no existe DATABASE_ENCRYPTION_KEY ni en keyring ni en archivo,
    se levanta RuntimeError impidiendo el arranque inseguro.
    """
    with patch.dict(os.environ, {"ALFONSO_ENV": "production", "DATABASE_ENCRYPTION_KEY": ""}):
        with patch("keyring.get_password", return_value=None):
            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(RuntimeError) as exc_info:
                    enc.get_or_create_key()
                
                assert "FATAL EN PRODUCCIÓN" in str(exc_info.value)
                assert "DATABASE_ENCRYPTION_KEY" in str(exc_info.value)


def test_encryption_key_success_in_production_with_key():
    """
    Verifica que en entorno de producción, si se proporciona DATABASE_ENCRYPTION_KEY,
    el arranque funciona correctamente y no se produce ningún error.
    """
    valid_32_bytes_b64 = "MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=" # 32 bytes en base64
    with patch.dict(os.environ, {"ALFONSO_ENV": "production", "DATABASE_ENCRYPTION_KEY": valid_32_bytes_b64}):
        with patch.object(enc, "KEY_PATH", enc.Path("data/test_non_existent.key")):
            key = enc.get_or_create_key()
            assert len(key) == 32
