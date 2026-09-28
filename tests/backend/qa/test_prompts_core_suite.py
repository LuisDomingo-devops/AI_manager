"""
Suite de QA para el generador de prompts del sistema (app/domain/prompt_generator.py).
Valida que la introspección de entorno de ejecución y metadatos de cliente sea tolerante a fallos
sin imports tardíos de error_logger.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, mock_open
from app.domain import prompt_generator

def test_prompt_generator_no_inline_error_logger_imports():
    """Verifica que prompt_generator.py no contenga imports tardíos de error_logger."""
    source = (Path(__file__).resolve().parents[3] / "app" / "domain" / "prompt_generator.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in source, (
        "prompt_generator.py aún contiene imports inline tardíos de error_logger"
    )

def test_get_client_context_str_corrupted_json_resilience():
    """Verifica que get_client_context_str degrade al contexto del servidor si last_client_info.json está corrupto."""
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="{corrupted_json: no_closing")):
        ctx_str = prompt_generator.get_client_context_str()
        assert "SYSTEM CONTEXT" in ctx_str
        assert "Operating System" in ctx_str

def test_get_client_context_str_wsl_check_resilience():
    """Verifica que la detección de WSL no falle si platform.uname() o el filesystem lanzan error."""
    with patch("os.path.exists", return_value=False), \
         patch("platform.uname", side_effect=OSError("Uname access error")):
        ctx_str = prompt_generator.get_client_context_str()
        assert "SYSTEM CONTEXT" in ctx_str
