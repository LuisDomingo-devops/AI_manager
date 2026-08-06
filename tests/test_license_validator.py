import json
import base64
import pytest
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes, serialization

from app.utils.license_validator import is_premium_license_valid, LICENSE_PATH

@pytest.fixture(autouse=True)
def clean_license_file():
    # Asegurar que el archivo de licencia no existe antes y después de cada test
    if LICENSE_PATH.exists():
        try:
            LICENSE_PATH.unlink()
        except Exception:
            pass
    yield
    if LICENSE_PATH.exists():
        try:
            LICENSE_PATH.unlink()
        except Exception:
            pass

def test_no_license_file():
    # Sin archivo de licencia, debe retornar False
    assert is_premium_license_valid() is False

def test_dev_bypass_env():
    # Si la variable de bypass de desarrollo está activa, debe retornar True
    with patch.dict("os.environ", {"ALFONSO_DEV_PREMIUM_BYPASS": "AlfonsoDevelopmentToken2026!"}):
        assert is_premium_license_valid() is True

def test_corrupted_license_signature():
    # Crear un archivo de licencia con firma inválida
    license_data = {
        "license_type": "premium",
        "holder": "Luis Domingo",
        "expires_at": "2029-12-31",
        "signature": "invalid_signature_base64"
    }
    LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_PATH.write_text(json.dumps(license_data), encoding="utf-8")
    
    assert is_premium_license_valid() is False

def test_invalid_license_type():
    # Criptográficamente correcta pero tipo incorrecto (ej: basic en vez de premium)
    # Generar claves RSA de prueba
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    
    payload = {
        "license_type": "basic",
        "holder": "Luis Domingo",
        "expires_at": "2029-12-31"
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = private_key.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
    signature_b64 = base64.b64encode(signature).decode("utf-8")
    payload["signature"] = signature_b64
    
    LICENSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    
    # Mockear la clave pública para que use nuestra clave de prueba
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        assert is_premium_license_valid() is False
