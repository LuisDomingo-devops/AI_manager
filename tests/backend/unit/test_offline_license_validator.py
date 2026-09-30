import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.core.license_validator import (
    OfflineLicenseValidator,
    LicenseStatusResult,
    generate_signed_license,
)

@pytest.fixture
def rsa_keypair():
    """Genera par de claves RSA para pruebas."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_key, public_pem

def test_offline_license_valid(tmp_path, rsa_keypair):
    private_key, public_pem = rsa_keypair
    license_file = tmp_path / "license.lic"
    clock_file = tmp_path / "clock.json"
    
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    license_dict = generate_signed_license(
        holder="Empresa Demo SL",
        expires_at=expires_at,
        license_type="pro",
        client_id="empresa-demo",
        machine_fingerprint="ALF-MACH-TEST1234",
        private_key=private_key,
    )
    license_file.write_text(json.dumps(license_dict), encoding="utf-8")
    
    validator = OfflineLicenseValidator(
        public_key_pem=public_pem,
        license_path=license_file,
        clock_path=clock_file,
    )
    
    result = validator.validate(
        current_dt=datetime.now(),
        override_machine_fingerprint="ALF-MACH-TEST1234",
    )
    
    assert result.is_operational is True
    assert result.status == "active"
    assert result.holder == "Empresa Demo SL"
    assert result.tier == "pro"
    assert result.days_until_expiration > 0

def test_offline_license_tampered_signature(tmp_path, rsa_keypair):
    private_key, public_pem = rsa_keypair
    license_file = tmp_path / "license.lic"
    clock_file = tmp_path / "clock.json"
    
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    license_dict = generate_signed_license(
        holder="Empresa Demo SL",
        expires_at=expires_at,
        license_type="pro",
        private_key=private_key,
    )
    # Alterar el payload para invalidar la firma
    license_dict["holder"] = "Empresa Hacker SL"
    license_file.write_text(json.dumps(license_dict), encoding="utf-8")
    
    validator = OfflineLicenseValidator(
        public_key_pem=public_pem,
        license_path=license_file,
        clock_path=clock_file,
    )
    result = validator.validate()
    assert result.is_operational is False
    assert result.status == "invalid_signature"

def test_offline_license_grace_period_and_expired(tmp_path, rsa_keypair):
    private_key, public_pem = rsa_keypair
    license_file = tmp_path / "license.lic"
    clock_file = tmp_path / "clock.json"
    
    # Expiró hace 2 días (dentro de gracia de 5 días)
    expires_at = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    license_dict = generate_signed_license(
        holder="Empresa Demo SL",
        expires_at=expires_at,
        license_type="basic",
        private_key=private_key,
    )
    license_file.write_text(json.dumps(license_dict), encoding="utf-8")
    
    validator = OfflineLicenseValidator(
        public_key_pem=public_pem,
        license_path=license_file,
        clock_path=clock_file,
    )
    result_grace = validator.validate(current_dt=datetime.now())
    assert result_grace.is_operational is True
    assert result_grace.status == "grace_period"
    assert result_grace.grace_days_remaining == 3

    # Expiró hace 10 días (fuera de gracia)
    expires_at_past = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    license_dict_past = generate_signed_license(
        holder="Empresa Demo SL",
        expires_at=expires_at_past,
        license_type="basic",
        private_key=private_key,
    )
    license_file.write_text(json.dumps(license_dict_past), encoding="utf-8")
    
    result_expired = validator.validate(current_dt=datetime.now())
    assert result_expired.is_operational is False
    assert result_expired.status == "expired"

def test_offline_license_machine_mismatch(tmp_path, rsa_keypair):
    private_key, public_pem = rsa_keypair
    license_file = tmp_path / "license.lic"
    clock_file = tmp_path / "clock.json"
    
    expires_at = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    license_dict = generate_signed_license(
        holder="Empresa Demo SL",
        expires_at=expires_at,
        license_type="advisor",
        machine_fingerprint="ALF-MACH-ORIGINAL",
        private_key=private_key,
    )
    license_file.write_text(json.dumps(license_dict), encoding="utf-8")
    
    validator = OfflineLicenseValidator(
        public_key_pem=public_pem,
        license_path=license_file,
        clock_path=clock_file,
    )
    result = validator.validate(
        current_dt=datetime.now(),
        override_machine_fingerprint="ALF-MACH-OTHER-PC",
    )
    assert result.is_operational is False
    assert result.status == "machine_mismatch"
