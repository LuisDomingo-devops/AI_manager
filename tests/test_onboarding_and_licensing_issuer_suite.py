import json
import pytest
from datetime import datetime
from starlette.testclient import TestClient
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.main import app
from admin_tools_private.license_issuer import PrivateLicenseIssuer
from app.utils.license_validator import (
    check_license_status,
    install_license,
    get_machine_fingerprint,
    LICENSE_PATH,
    CLOCK_INTEGRITY_PATH
)

client = TestClient(app)

@pytest.fixture(autouse=True)
def clean_env():
    """Limpia los archivos de prueba antes y después."""
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
def master_keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    pub_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_key, pub_pem

def test_private_license_issuer_paid_and_trial(master_keypair):
    """
    Verifica que el emisor privado firme licencias mensuales y de prueba (Trial 14 días)
    y que el validador del cliente las reconozca como 100% legítimas y operativas.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    # 1. Emitir licencia de pago mensual (1 mes)
    paid_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Desarrollos Digitales S.L.",
        client_id="desarrollos_01",
        machine_fingerprint=local_fp,
        months=1,
        private_key=private_key
    )
    assert paid_lic["holder"] == "Desarrollos Digitales S.L."
    assert paid_lic["machine_fingerprint"] == local_fp
    assert "signature" in paid_lic

    # Instalar y verificar en el cliente
    install_license(paid_lic)
    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        res_paid = check_license_status(ignore_dev_bypass=True)
        assert res_paid.status == "active"
        assert res_paid.is_operational is True
        assert res_paid.days_until_expiration >= 28

    # 2. Emitir licencia de prueba de 14 días
    trial_lic = PrivateLicenseIssuer.issue_trial_license(
        holder="Usuario Prueba",
        machine_fingerprint=local_fp,
        days=14,
        private_key=private_key
    )
    assert trial_lic["is_trial"] is True
    assert "Prueba Gratuita" in trial_lic["holder"]

    install_license(trial_lic)
    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        res_trial = check_license_status(ignore_dev_bypass=True)
        assert res_trial.status == "active"
        assert res_trial.is_operational is True
        assert res_trial.days_until_expiration >= 13

def test_private_license_issuer_transfer(master_keypair):
    """
    Verifica que el emisor privado permita transferir una licencia existente
    a una nueva máquina (Machine Binding Transfer).
    """
    private_key, pub_pem = master_keypair
    old_fp = "ALF-MACH-OLD11111111"
    new_fp = "ALF-MACH-NEW22222222"

    orig_lic = PrivateLicenseIssuer.issue_paid_license(
        holder="Consultora Global",
        client_id="consultora_01",
        machine_fingerprint=old_fp,
        months=2,
        private_key=private_key
    )

    # Transferir a new_fp
    transferred_lic = PrivateLicenseIssuer.transfer_license(
        existing_license=orig_lic,
        new_machine_fingerprint=new_fp,
        private_key=private_key
    )
    assert transferred_lic["machine_fingerprint"] == new_fp
    assert "signature" in transferred_lic

    # En el equipo nuevo debe funcionar, en el viejo debe fallar
    install_license(transferred_lic)
    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        # En equipo nuevo -> OK
        status_new = check_license_status(ignore_dev_bypass=True, override_machine_fingerprint=new_fp)
        assert status_new.status == "active"
        assert status_new.is_operational is True

        # En equipo viejo -> Machine Mismatch
        status_old = check_license_status(ignore_dev_bypass=True, override_machine_fingerprint=old_fp)
        assert status_old.status == "machine_mismatch"
        assert status_old.is_operational is False

def test_onboarding_wizard_full_flow(master_keypair):
    """
    Verifica el flujo completo del Onboarding Wizard en 3 pasos:
    1. Consulta de estado y textos legales EULA.
    2. Rechazo si no se acepta el EULA.
    3. Inicialización fiscal completa y activación de licencia.
    """
    private_key, pub_pem = master_keypair
    local_fp = get_machine_fingerprint()

    # 1. Consultar textos legales EULA
    res_eula = client.get("/api/v1/onboarding/eula")
    assert res_eula.status_code == 200
    assert "CONTRATO DE LICENCIA DE USUARIO FINAL" in res_eula.json()["eula_text"]

    # 2. Consultar estado inicial
    res_init = client.get("/api/v1/onboarding/status")
    assert res_init.status_code == 200
    assert res_init.json()["machine_fingerprint"] == local_fp

    # 3. Intentar setup sin aceptar EULA -> Error 400
    bad_payload = {
        "client_id": "test_onboarding_client",
        "razon_social": "Arquitectura y Urbanismo S.L.",
        "nif": "B12998877",
        "regimen_iva": "general",
        "irpf_rate_default": 15.0,
        "eula_accepted": False
    }
    res_bad = client.post("/api/v1/onboarding/setup", json=bad_payload)
    assert res_bad.status_code == 400
    assert "obligatorio aceptar los Términos y Condiciones" in res_bad.json()["detail"]

    # 4. Setup exitoso con emisión de licencia trial
    trial_lic = PrivateLicenseIssuer.issue_trial_license(
        holder="Arquitectura y Urbanismo S.L.",
        machine_fingerprint=local_fp,
        days=14,
        private_key=private_key
    )

    good_payload = {
        "client_id": "test_onboarding_client",
        "razon_social": "Arquitectura y Urbanismo S.L.",
        "nif": "B12998877",
        "direccion": "Calle Mayor 10, Madrid",
        "epigrafe_iae": "8431",
        "regimen_iva": "general",
        "irpf_rate_default": 15.0,
        "license_data": trial_lic,
        "eula_accepted": True
    }

    with patch("app.utils.license_validator.PUBLIC_KEY_PEM", pub_pem):
        res_good = client.post("/api/v1/onboarding/setup", json=good_payload)
        assert res_good.status_code == 200
        data_good = res_good.json()
        assert data_good["status"] == "ok"
        assert "Configuración inicial completada" in data_good["message"]

        # 5. Comprobar que el status ahora marca onboarding completado
        res_after = client.get("/api/v1/onboarding/status?client_id=test_onboarding_client")
        assert res_after.status_code == 200
        after_data = res_after.json()
        assert after_data["is_onboarding_completed"] is True
        assert after_data["profile_configured"] is True
        assert after_data["profile"]["razon_social"] == "Arquitectura y Urbanismo S.L."
        assert after_data["license"]["is_operational"] is True
