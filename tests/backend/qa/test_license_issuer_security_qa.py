import base64
import json
import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from admin_tools_private.license_issuer import PrivateLicenseIssuer

def test_license_tampering_detected_qa(valid_rsa_key_pair):
    """QA de Seguridad: Detectar manipulaciones del payload en licencias emitidas."""
    pkey = valid_rsa_key_pair["private_key"]
    pubkey = pkey.public_key()

    license_data = PrivateLicenseIssuer.issue_paid_license(
        holder="Usuario Original",
        client_id="usr_01",
        machine_fingerprint="ORIGINAL_MACHINE_ID",
        months=1,
        private_key=pkey
    )

    # Intento de falsificación: Modificar fecha de caducidad o titular sin re-firmar
    tampered_payload = {
        "license_type": license_data["license_type"],
        "holder": "Usuario Falsificado",
        "expires_at": "2099-12-31",
        "machine_fingerprint": license_data["machine_fingerprint"]
    }
    tampered_bytes = json.dumps(tampered_payload, sort_keys=True).encode("utf-8")
    signature = base64.b64decode(license_data["signature"])

    with pytest.raises(InvalidSignature):
        pubkey.verify(
            signature,
            tampered_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )


def test_license_transfer_flow_security_qa(valid_rsa_key_pair):
    """QA de Seguridad: Transferencia legítima de licencia a nueva máquina con re-firma válida."""
    pkey = valid_rsa_key_pair["private_key"]
    pubkey = pkey.public_key()

    original = PrivateLicenseIssuer.issue_paid_license(
        holder="Cliente Premium",
        client_id="client_777",
        machine_fingerprint="OLD_MACHINE_001",
        months=6,
        private_key=pkey
    )

    transferred = PrivateLicenseIssuer.transfer_license(
        existing_license=original,
        new_machine_fingerprint="NEW_MACHINE_002",
        private_key=pkey
    )

    assert transferred["machine_fingerprint"] == "NEW_MACHINE_002"
    assert transferred["signature"] != original["signature"], "La firma debe actualizarse al cambiar el hardware"

    payload = {
        "license_type": transferred["license_type"],
        "holder": transferred["holder"],
        "expires_at": transferred["expires_at"],
        "machine_fingerprint": "NEW_MACHINE_002"
    }
    payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
    signature = base64.b64decode(transferred["signature"])

    pubkey.verify(
        signature,
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256()
    )
