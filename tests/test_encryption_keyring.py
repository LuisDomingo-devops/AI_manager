import os
import base64
from unittest.mock import patch, MagicMock
from pathlib import Path
import pytest

from app.utils.encryption import get_or_create_key, KEY_PATH

@pytest.fixture(autouse=True)
def clean_local_key():
    # Asegurar que el archivo local de clave no existe antes y después de cada test
    if KEY_PATH.exists():
        try:
            KEY_PATH.unlink()
        except Exception:
            pass
    yield
    if KEY_PATH.exists():
        try:
            KEY_PATH.unlink()
        except Exception:
            pass

def test_keyring_storage_success():
    # 1. Simular que keyring funciona correctamente
    keyring_store = {}
    
    def mock_get(service, username):
        return keyring_store.get(f"{service}:{username}")
        
    def mock_set(service, username, password):
        keyring_store[f"{service}:{username}"] = password

    with patch("keyring.get_password", side_effect=mock_get), \
         patch("keyring.set_password", side_effect=mock_set):
         
        # Primera llamada genera clave
        key1 = get_or_create_key()
        assert len(key1) == 32
        # No debe haber creado el archivo local
        assert not KEY_PATH.exists()
        
        # Debe haberse guardado en el keyring
        stored_b64 = keyring_store.get("alfonso_autonomo:db_encryption_key")
        assert stored_b64 is not None
        assert base64.b64decode(stored_b64.encode('utf-8')) == key1
        
        # Segunda llamada recupera la misma clave
        key2 = get_or_create_key()
        assert key2 == key1

def test_keyring_failure_fallback_to_file():
    # 1. Simular que keyring arroja un error (ej. entorno CI/sin GUI)
    def mock_get_error(service, username):
        raise RuntimeError("No keyring backend available")
        
    def mock_set_error(service, username, password):
        raise RuntimeError("No keyring backend available")

    with patch("keyring.get_password", side_effect=mock_get_error), \
         patch("keyring.set_password", side_effect=mock_set_error):
         
        # Primera llamada genera clave
        key1 = get_or_create_key()
        assert len(key1) == 32
        # Debe haber creado el archivo local como fallback
        assert KEY_PATH.exists()
        assert KEY_PATH.read_bytes() == key1
        
        # Segunda llamada recupera la misma clave del archivo
        key2 = get_or_create_key()
        assert key2 == key1
