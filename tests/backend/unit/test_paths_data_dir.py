import pytest
from pathlib import Path

def test_data_dir_exists_in_app_utils_paths():
    """
    Verifica que DATA_DIR está definido y exportado en app.utils.paths,
    es de tipo Path y apunta a un directorio existente.
    """
    from app.utils.paths import DATA_DIR

    assert isinstance(DATA_DIR, Path), "DATA_DIR debe ser una instancia de pathlib.Path"
    assert DATA_DIR.name == "data", "DATA_DIR debe llamarse 'data'"
    assert DATA_DIR.exists(), f"El directorio DATA_DIR ({DATA_DIR}) debe existir físicamente"
    assert DATA_DIR.is_dir(), f"DATA_DIR ({DATA_DIR}) debe ser un directorio"
