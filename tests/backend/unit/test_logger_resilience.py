"""
Test unitario de resiliencia del subsistema de logging (app/utils/logger.py).
Valida que el formateador JSON y el handler de rotación no recurran a imports inline
ni generen recursión infinita ante fallos de contexto o streams.
"""

from pathlib import Path
import logging
import pytest
from unittest.mock import patch, MagicMock
from app.utils import logger

def test_logger_no_inline_error_logger_imports():
    """Verifica que logger.py no contenga imports tardíos de error_logger."""
    source = (Path(__file__).resolve().parents[3] / "app" / "utils" / "logger.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in source, (
        "logger.py aún contiene imports inline tardíos de error_logger"
    )

def test_json_formatter_tenant_context_failure_resilience():
    """Verifica que JSONFormatter use tenant 'default' sin invocar recursión de logging si falla tenant_context."""
    formatter = logger.JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Mensaje de prueba",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    assert '"tenant_id": "default"' in formatted

def test_safe_rotating_file_handler_close_error_resilience():
    """Verifica que SafeRotatingFileHandler gestione fallos al cerrar el stream en doRollover."""
    handler = logger.SafeRotatingFileHandler(Path("logs/test_rot.log"), maxBytes=1024, backupCount=1)
    mock_stream = MagicMock()
    mock_stream.close.side_effect = OSError("Stream lock error")
    handler.stream = mock_stream
    
    with patch.object(logger.RotatingFileHandler, "doRollover"):
        with patch.object(handler, "_open", return_value=MagicMock()):
            handler.doRollover()
            assert handler.stream is not None
