import os
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from admin_tools_private.license_issuer import PrivateLicenseIssuer

def test_get_master_private_key_rejects_corrupted_pem():
    """Valida que una cadena PEM corrupta o sintética sea rechazada con ValueError."""
    corrupted_pem = b"""-----BEGIN RSA PRIVATE KEY-----
L7p6vV/zL+Yt0v1p3q2rK8s7tY+w4x3a1b5c9d8e7f6a5b4c3d2e1f0a9b8c7d6e
5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a
-----END RSA PRIVATE KEY-----"""
    with pytest.raises(ValueError, match="Clave privada maestra RSA inválida o corrupta"):
        PrivateLicenseIssuer.get_master_private_key(custom_pem=corrupted_pem)


def test_get_master_private_key_loads_valid_rsa_key(valid_rsa_key_pair):
    """Valida que una clave RSA matemáticamente válida se cargue correctamente."""
    key = PrivateLicenseIssuer.get_master_private_key(custom_pem=valid_rsa_key_pair["private_pem"])
    assert isinstance(key, rsa.RSAPrivateKey)
    assert key.key_size >= 2048


def test_no_hardcoded_corrupted_default_key_exists():
    """Valida que la constante hardcodeada con texto ficticio no exista o no sea usada."""
    import admin_tools_private.license_issuer as module
    default_key = getattr(module, "DEFAULT_MASTER_PRIVATE_KEY_PEM", None)
    assert default_key is None, "La constante DEFAULT_MASTER_PRIVATE_KEY_PEM corrupta debe ser eliminada"


def test_get_master_private_key_raises_runtime_error_when_unconfigured(monkeypatch):
    """Valida que sin variable de entorno ni clave proporcionada, el sistema deniegue la inicialización."""
    monkeypatch.delenv("ALFONSO_MASTER_PRIVATE_KEY_PEM", raising=False)
    with pytest.raises(RuntimeError, match="No se ha configurado una clave privada maestra RSA válida"):
        PrivateLicenseIssuer.get_master_private_key()
