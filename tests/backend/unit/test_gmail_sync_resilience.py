"""
Test unitario de resiliencia en sincronización de correo (gmail_sync).
Verifica que las excepciones al acceder a keyring o en decodificación
se gestionen de forma tipada sin imports tardíos de error_logger.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.adapters import gmail_sync

def test_gmail_sync_no_inline_error_logger_imports():
    """Verifica que gmail_sync.py no contenga imports tardíos de error_logger."""
    source = (Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "adapters" / "gmail_sync.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in source, (
        "gmail_sync.py aún contiene imports inline tardíos de error_logger"
    )

def test_gmail_sync_keyring_failure_resilience(monkeypatch):
    """Verifica que _sync_from_gmail_blocking tolere fallos de backend de keyring."""
    monkeypatch.setenv("GMAIL_EMAIL", "test@alfonso.ai")
    monkeypatch.delenv("GMAIL_APP_PASSWORD", raising=False)
    
    with patch("keyring.get_password", side_effect=OSError("Keyring backend unavailable")):
        count = gmail_sync._sync_from_gmail_blocking()
        assert count == 0
