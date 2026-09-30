import ast
import warnings
from pathlib import Path
import pytest

def test_excel_sync_service_imports_from_canonical_connection_manager():
    """Valida que excel_sync.py importe directamente de app.infrastructure.database.connection_manager."""
    file_path = Path("app/domain/services/excel_sync.py")
    assert file_path.exists(), "excel_sync.py no existe"
    
    content = file_path.read_text(encoding="utf-8")
    assert "app.adapters.memory" not in content, (
        "excel_sync.py todavía contiene importaciones de la capa obsoleta 'app.adapters.memory'"
    )
    assert "from app.infrastructure.database.connection_manager import" in content, (
        "excel_sync.py debe importar directamente de 'app.infrastructure.database.connection_manager'"
    )


def test_legacy_adapters_memory_emits_deprecation_warning():
    """Valida que importar app.adapters.memory.memory emita una advertencia formal de deprecación."""
    import importlib
    import sys
    
    # Asegurar recarga para capturar la advertencia de importación
    sys.modules.pop("app.adapters.memory.memory", None)
    
    with pytest.deprecated_call():
        importlib.import_module("app.adapters.memory.memory")


def test_legacy_adapters_vector_memory_emits_deprecation_warning():
    """Valida que importar app.adapters.memory.vector_memory emita advertencia formal de deprecación."""
    import importlib
    import sys
    
    sys.modules.pop("app.adapters.memory.vector_memory", None)
    
    with pytest.deprecated_call():
        importlib.import_module("app.adapters.memory.vector_memory")
