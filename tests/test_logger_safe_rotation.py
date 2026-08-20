"""
Tests Unitarios, Integración y QA para SafeRotatingFileHandler y Logging Estructurado.
Verifica que no ocurra PermissionError [WinError 32] en Windows durante rotaciones concurrentes.
"""
import os
import tempfile
import logging
from pathlib import Path
import pytest
from app.utils.logger import SafeRotatingFileHandler, JSONFormatter, app_logger, get_shared_json_handler

def test_safe_rotating_file_handler_handles_rollover_without_error():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test.log"
        # Handler con tamaño muy pequeño (50 bytes) para forzar rotaciones constantes
        handler = SafeRotatingFileHandler(log_file, maxBytes=50, backupCount=3, encoding="utf-8")
        logger = logging.getLogger("test_safe_rotation")
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        for i in range(20):
            logger.info(f"Mensaje de prueba con longitud suficiente para rotar {i}")

        handler.close()
        assert log_file.exists()


def test_safe_rotating_file_handler_simulated_permission_error(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        log_file = Path(tmpdir) / "test_perm.log"
        handler = SafeRotatingFileHandler(log_file, maxBytes=50, backupCount=2, encoding="utf-8")

        # Simular PermissionError en os.rename (WinError 32)
        def mock_rename(src, dst):
            raise PermissionError("[WinError 32] Archivo bloqueado por otro proceso")

        monkeypatch.setattr(os, "rename", mock_rename)

        logger = logging.getLogger("test_perm_error")
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        # No debe lanzar excepción ni romper la ejecución
        logger.info("Este mensaje provoca un rollover que fallaría en RotatingFileHandler estándar")
        logger.info("Segundo mensaje de prueba")

        handler.close()


def test_shared_json_handler_singleton():
    h1 = get_shared_json_handler()
    h2 = get_shared_json_handler()
    assert h1 is h2
    assert isinstance(h1, SafeRotatingFileHandler)


def test_app_logger_emits_valid_json_log():
    record = logging.LogRecord(
        name="app",
        level=logging.INFO,
        pathname="app/main.py",
        lineno=100,
        msg="Prueba observabilidad JSON",
        args=(),
        exc_info=None
    )
    formatter = JSONFormatter()
    formatted = formatter.format(record)
    assert "timestamp" in formatted
    assert "level" in formatted
    assert "Prueba observabilidad JSON" in formatted
