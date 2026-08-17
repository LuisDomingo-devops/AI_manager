import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from starlette.testclient import TestClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from app.utils.license_validator import (
    check_license_status,
    is_premium_license_valid,
    install_license,
    generate_signed_license,
    LICENSE_PATH,
    CLOCK_INTEGRITY_PATH
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_license_env():
    """Limpia los archivos de licencia e integridad antes y después de cada prueba."""
    for p in (LICENSE_PATH, CLOCK_INTEGRITY_PATH):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    yield
    for p in (LICENSE_PATH, CLOCK_INTEGRITY_PATH):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, pub_pem

def test_license_active_within_month(rsa_keypair):
    """
    Verifica que una licencia dentro de su mes de vigencia devuelva estado 'active'
    y esté 100% operativa.
    """
    private_key, pub_pem = rsa_keypair
    license_data = generate_signed_license(
        holder="Ana Gómez Arquitectura",
        client_id="ana_gomez_01",
        expires_at="2026-08-30",
        license_type="premium",
        private_key=private_key
    )
    install_license(license_data)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        status = check_license_status(current_dt=datetime(2026, 8, 17, 10, 0), ignore_dev_bypass=True)
        assert status.status == "active"
        assert status.is_operational is True
        assert status.days_until_expiration == 13
        assert status.grace_days_remaining == 5
        assert is_premium_license_valid() is True

def test_license_grace_period_day_2(rsa_keypair):
    """
    Verifica que si la cuota mensual venció hace 2 días (ej: día 15 y hoy es día 17),
    la licencia entre en estado 'grace_period', SIGA OPERATIVA (is_operational=True)
    y reporte 3 días restantes de cortesía de los 5 iniciales.
    """
    private_key, pub_pem = rsa_keypair
    license_data = generate_signed_license(
        holder="Carlos Ruiz Consulting",
        client_id="carlos_ruiz_01",
        expires_at="2026-08-15",
        license_type="premium",
        private_key=private_key
    )
    install_license(license_data)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        status = check_license_status(current_dt=datetime(2026, 8, 17, 10, 0), ignore_dev_bypass=True)
        assert status.status == "grace_period"
        assert status.is_operational is True
        assert status.grace_days_remaining == 3
        assert "período de gracia" in status.message
        # Comprobar que a nivel de sistema se considera válida para operar
        assert is_premium_license_valid() is True

def test_license_expired_after_grace_period(rsa_keypair):
    """
    Verifica que pasados los 5 días de gracia (ej: venció hace 7 días),
    el estado pase a 'expired' y se bloquee la operatividad (is_operational=False).
    """
    private_key, pub_pem = rsa_keypair
    license_data = generate_signed_license(
        holder="Marta Sánchez Diseño",
        client_id="marta_sanchez_01",
        expires_at="2026-08-10",
        license_type="premium",
        private_key=private_key
    )
    install_license(license_data)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        status = check_license_status(current_dt=datetime(2026, 8, 17, 10, 0), ignore_dev_bypass=True)
        assert status.status == "expired"
        assert status.is_operational is False
        assert status.grace_days_remaining == 0
        assert "han expirado" in status.message
        assert is_premium_license_valid() is False

def test_clock_tampering_protection(rsa_keypair):
    """
    Verifica que si el usuario retrasa el reloj del sistema respecto a la última ejecución,
    se detecte la manipulación (clock_tampered) y se inhabilite la ejecución.
    """
    private_key, pub_pem = rsa_keypair
    license_data = generate_signed_license(
        holder="Test Tampering",
        expires_at="2026-08-30",
        private_key=private_key
    )
    install_license(license_data)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        # 1. Ejecución en tiempo normal (2026-08-17) -> OK
        status_ok = check_license_status(current_dt=datetime(2026, 8, 17, 12, 0), ignore_dev_bypass=True)
        assert status_ok.status == "active"
        assert status_ok.is_operational is True

        # 2. Intento de retrasar el reloj a 2025 -> Clock tampered!
        status_tampered = check_license_status(current_dt=datetime(2025, 1, 1, 12, 0), ignore_dev_bypass=True)
        assert status_tampered.status == "clock_tampered"
        assert status_tampered.is_operational is False

def test_api_license_status_and_activation(rsa_keypair):
    """
    Verifica los endpoints de la API para activar licencia e inspeccionar el estado.
    """
    private_key, pub_pem = rsa_keypair
    license_data = generate_signed_license(
        holder="Empresa API Activa",
        client_id="empresa_api_01",
        expires_at="2026-09-30",
        private_key=private_key
    )

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        # 1. Activar licencia vía POST
        res_act = client.post("/api/v1/subscriptions/activate-license", json={"license_data": license_data})
        assert res_act.status_code == 200
        data_act = res_act.json()
        assert data_act["installed"] is True
        assert data_act["license"]["status"] == "active"

        # 2. Consultar estado vía GET
        res_status = client.get("/api/v1/subscriptions/license-status")
        assert res_status.status_code == 200
        data_status = res_status.json()
        assert data_status["license"]["status"] == "active"
        assert data_status["license"]["holder"] == "Empresa API Activa"
        assert data_status["license"]["is_operational"] is True

def test_machine_binding_match_and_mismatch(rsa_keypair):
    """
    Verifica que la vinculación de hardware (Machine Binding) permita operar en el equipo original
    y bloquee la ejecución si el archivo de licencia se copia a otra máquina.
    """
    private_key, pub_pem = rsa_keypair
    original_fp = "ALF-MACH-ORIGINAL0001"
    stolen_fp = "ALF-MACH-PIRATE000002"

    # Licencia firmada y enlazada a la máquina original
    license_data = generate_signed_license(
        holder="Estudio Creativo S.L.",
        client_id="estudio_01",
        expires_at="2026-09-30",
        machine_fingerprint=original_fp,
        private_key=private_key
    )
    install_license(license_data)

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        # 1. En la máquina original -> Operatividad total
        status_orig = check_license_status(
            current_dt=datetime(2026, 8, 17, 10, 0),
            ignore_dev_bypass=True,
            override_machine_fingerprint=original_fp
        )
        assert status_orig.status == "active"
        assert status_orig.is_operational is True

        # 2. En una máquina distinta (archivo copiado) -> Bloqueo por Machine Mismatch
        status_mismatch = check_license_status(
            current_dt=datetime(2026, 8, 17, 10, 0),
            ignore_dev_bypass=True,
            override_machine_fingerprint=stolen_fp
        )
        assert status_mismatch.status == "machine_mismatch"
        assert status_mismatch.is_operational is False
        assert "vinculada a otro ordenador" in status_mismatch.message

def test_api_machine_fingerprint_endpoint():
    """
    Verifica el endpoint GET /api/v1/subscriptions/machine-fingerprint
    """
    res = client.get("/api/v1/subscriptions/machine-fingerprint")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "machine_fingerprint" in data
    assert data["machine_fingerprint"].startswith("ALF-MACH-")
