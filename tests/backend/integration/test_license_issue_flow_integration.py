import base64
import json
import pytest
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from admin_tools_private.license_issuer import PrivateLicenseIssuer

def test_license_issue_paid_flow_integration(valid_rsa_key_pair):
    """Flujo de integración para emisión de licencia pagada y verificación de firma digital."""
    pkey = valid_rsa_key_pair["private_key"]
    pubkey = pkey.public_key()
    
    license_data = PrivateLicenseIssuer.issue_paid_license(
        holder="Despacho Fiscal SL",
        client_id="client_1234",
        machine_fingerprint="FINGERPRINT_HARDWARE_XYZ",
        months=3,
        license_type="premium",
        private_key=pkey
    )
    
    assert license_data["holder"] == "Despacho Fiscal SL"
    assert license_data["license_type"] == "premium"
    assert "signature" in license_data
    
    # Reconstrucción del payload para validación criptográfica matemática
    payload = {
        "license_type": license_data["license_type"],
        "holder": license_data["holder"],
        "expires_at": license_data["expires_at"],
        "machine_fingerprint": license_data["machine_fingerprint"]
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = base64.b64decode(license_data["signature"])
    
    # La verificación no debe lanzar InvalidSignature
    pubkey.verify(
        signature,
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )


def test_license_issue_trial_flow_integration(valid_rsa_key_pair):
    """Flujo de integración para emisión de licencia de prueba de 14 días."""
    pkey = valid_rsa_key_pair["private_key"]
    pubkey = pkey.public_key()
    
    trial_data = PrivateLicenseIssuer.issue_trial_license(
        holder="Autónomo de Prueba",
        machine_fingerprint="FINGERPRINT_TRIAL_ABC",
        days=14,
        private_key=pkey
    )
    
    assert trial_data["is_trial"] is True
    signature = base64.b64decode(trial_data["signature"])
    
    payload = {
        "license_type": "premium",
        "holder": trial_data["holder"],
        "expires_at": trial_data["expires_at"],
        "machine_fingerprint": trial_data["machine_fingerprint"]
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    
    pubkey.verify(
        signature,
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
