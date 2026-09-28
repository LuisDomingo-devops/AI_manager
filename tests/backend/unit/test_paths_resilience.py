"""
Test unitario de resiliencia para la resolución de rutas del sistema (app/utils/paths.py).
Valida que la lectura de metadatos del cliente maneje JSON corruptos sin capturas ciegas
ni imports tardíos de error_logger.
"""

from pathlib import Path
import pytest
from unittest.mock import patch
from app.utils import paths

def test_paths_no_inline_error_logger_imports():
    """Verifica que paths.py no contenga imports tardíos de error_logger."""
    source = (Path(__file__).resolve().parents[3] / "app" / "utils" / "paths.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in source, (
        "paths.py aún contiene imports inline tardíos de error_logger"
    )

def test_get_execution_context_corrupt_info_file_resilience(tmp_path, monkeypatch):
    """Verifica que get_client_context degrade al entorno del servidor si el archivo JSON está corrupto."""
    corrupt_file = tmp_path / "last_client_info.json"
    corrupt_file.write_text("{corrupt: true", encoding="utf-8")
    
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_text", return_value="{corrupt: true"):
        info = paths.get_client_context("non_existent_client")
        assert "system" in info
        assert "username" in info
        assert "home" in info
