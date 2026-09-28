"""
Test unitario de resiliencia del validador de licencias y huella digital del sistema.
Verifica que los fallos de lectura de registro, identificación de máquina y reloj
se manejen con excepciones tipadas (OSError, json.JSONDecodeError, etc.) sin AI-slop ni imports inline.
"""

import inspect
import json
import pytest
from unittest.mock import patch, mock_open
from app.utils import license_validator

def test_license_validator_no_inline_error_logger_imports():
    """Verifica que license_validator no importe inline error_logger en bloques except."""
    source = inspect.getsource(license_validator)
    assert '    from app.utils.logger import error_logger' not in source, (
        "license_validator.py aún contiene imports inline tardíos de error_logger"
    )

def test_get_machine_fingerprint_resilience_on_registry_error(monkeypatch):
    """Verifica que get_machine_fingerprint genera huella ante errores de registro del sistema."""
    # Simular fallo en winreg si estamos en Windows o forzar platform a Windows
    monkeypatch.setattr(license_validator.platform, "system", lambda: "Windows")
    with patch("winreg.OpenKey", side_effect=OSError("Access denied to registry")):
        fp = license_validator.get_machine_fingerprint()
        assert fp.startswith("ALF-MACH-")
        assert len(fp) > 10

def test_check_clock_integrity_corrupted_json(tmp_path, monkeypatch):
    """Verifica resiliencia ante archivo de reloj corrupto con JSONDecodeError."""
    fake_clock = tmp_path / "corrupt_clock.json"
    fake_clock.write_text("{corrupt_json: invalid", encoding="utf-8")
    monkeypatch.setattr(license_validator, "CLOCK_INTEGRITY_PATH", fake_clock)
    
    # Debe manejar la corrupción sin crashear y actualizar el reloj
    result = license_validator.check_clock_integrity()
    assert result is True
