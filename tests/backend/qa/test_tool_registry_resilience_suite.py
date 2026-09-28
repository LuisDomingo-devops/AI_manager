"""
Suite de QA de registro y descubrimiento de herramientas (tool_registry).
Valida que la introspección dinámica de firmas y generación de esquemas
maneje errores de análisis de parámetros sin imports tardíos de error_logger.
"""

from pathlib import Path
import inspect
import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.adapters import tool_registry

def test_tool_registry_no_inline_error_logger_imports():
    """Verifica que tool_registry.py no contenga imports tardíos de error_logger."""
    source = (Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "adapters" / "tool_registry.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in source, (
        "tool_registry.py aún contiene imports inline tardíos de error_logger"
    )

def test_tool_registry_generate_schemas_broken_signature_resilience():
    """Verifica que get_tool_schemas maneje funciones con firmas anómalas sin romper el catálogo."""
    tool_registry.load_plugins()

    def dummy_broken_func(*args, **kwargs):
        pass

    real_signature = inspect.signature

    def mock_signature(f):
        if f == dummy_broken_func:
            raise TypeError("Cannot inspect built-in or complex object")
        return real_signature(f)

    with patch.dict(tool_registry.SERVER_TOOLS, {"broken_tool": dummy_broken_func}, clear=False):
        with patch("inspect.signature", side_effect=mock_signature):
            schemas = tool_registry.get_tool_schemas()
            assert isinstance(schemas, list)
            broken_schemas = [s for s in schemas if s.get("function", {}).get("name") == "broken_tool"]
            assert len(broken_schemas) == 1
            assert broken_schemas[0]["function"]["parameters"]["properties"] == {}
