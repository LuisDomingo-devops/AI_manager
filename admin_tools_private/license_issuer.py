import os
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization

# Clave privada maestra RSA de desarrollo/ejemplo de Alfonso S.L.
# En producción comercial en la nube, esta clave se inyecta mediante variables de entorno secretas (ENV_VARS)
DEFAULT_MASTER_PRIVATE_KEY_PEM = b"""-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA4vxqcQyYeJuz3wEr1IRZQJ70ygRTchcOqNroZYZRSEM0ngBL
l8S/J24Vy0Me/j4mjmWJo75NO7UsDXCTll9EGBDD+PEYoSsIIre1l6RNqI31iBTe
taIcbjKiQ9P7ExYWflhPH8N0Xm5ESPktQw7WQ8NJHdR1/ovUdEC3EC1hjac3HcNt
Egcpwc3HZtIds7+QuQTFaHxyMFCpovUnmddYsEVP8t0jwc9TiXc3BcnCIqJyx3ym
vIyEM23wMrl1mpG07PQkn0jO0sY8ThwyXqM0Oum6lYfIVVrzBeciDHky82Q60xyq
paArkXRu2zqBnXaa0/FHzRAuGUn38NN58W4xlwIDAQABAoIBAQCZ3V3k9qjL3q7n
L7p6vV/zL+Yt0v1p3q2rK8s7tY+w4x3a1b5c9d8e7f6a5b4c3d2e1f0a9b8c7d6e
5f4a3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a
3b2c1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c
1d0e9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e
9f8a7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a
7b6c5d4e3f2a1b0c9d8e7f6a5b4c3d2e1f0a9b8c7d6e5f4a3b2c1d0e9f8a7b6c
-----END RSA PRIVATE KEY-----"""

class PrivateLicenseIssuer:
    """
    EMISOR PRIVADO DE LICENCIAS (SOLO PARA USO DEL FABRICANTE / SERVIDOR EN LA NUBE).
    Este módulo NUNCA se distribuye a los clientes finales.
    
    Responsabilidades:
    1. Firmar licencias mensuales tras confirmación de pago en Stripe.
    2. Emitir licencias de prueba (Trial 14 días) enlazadas al hardware del usuario.
    3. Gestionar transferencias de licencia si el cliente cambia de ordenador.
    """

    @classmethod
    def get_master_private_key(cls, custom_pem: Optional[bytes] = None) -> rsa.RSAPrivateKey:
        """Carga la clave privada maestra de firma."""
        pem_bytes = custom_pem or os.getenv("ALFONSO_MASTER_PRIVATE_KEY_PEM", "").encode("utf-8") or DEFAULT_MASTER_PRIVATE_KEY_PEM
        return serialization.load_pem_private_key(pem_bytes, password=None)

    @classmethod
    def issue_paid_license(
        cls,
        holder: str,
        client_id: str,
        machine_fingerprint: str,
        months: int = 1,
        license_type: str = "premium",
        private_key: Optional[rsa.RSAPrivateKey] = None
    ) -> Dict[str, Any]:
        """
        Emite una licencia mensual tras el cobro exitoso en Stripe.
        """
        pkey = private_key or cls.get_master_private_key()
        now = datetime.now()
        # Vencimiento a N meses (30 días por mes)
        exp_date = (now + timedelta(days=30 * months)).strftime("%Y-%m-%d")

        payload = {
            "license_type": license_type,
            "holder": holder,
            "expires_at": exp_date,
            "machine_fingerprint": machine_fingerprint
        }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = pkey.sign(
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "license_type": license_type,
            "holder": holder,
            "client_id": client_id,
            "expires_at": exp_date,
            "machine_fingerprint": machine_fingerprint,
            "issued_at": now.strftime("%Y-%m-%d"),
            "signature": signature_b64
        }

    @classmethod
    def issue_trial_license(
        cls,
        holder: str,
        machine_fingerprint: str,
        days: int = 14,
        private_key: Optional[rsa.RSAPrivateKey] = None
    ) -> Dict[str, Any]:
        """
        Emite una licencia de prueba gratuita de 14 días enlazada al hardware del usuario.
        """
        pkey = private_key or cls.get_master_private_key()
        now = datetime.now()
        exp_date = (now + timedelta(days=days)).strftime("%Y-%m-%d")

        payload = {
            "license_type": "premium",
            "holder": f"{holder} (Prueba Gratuita {days} días)",
            "expires_at": exp_date,
            "machine_fingerprint": machine_fingerprint
        }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = pkey.sign(
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "license_type": "premium",
            "holder": payload["holder"],
            "client_id": "trial_user",
            "expires_at": exp_date,
            "machine_fingerprint": machine_fingerprint,
            "is_trial": True,
            "issued_at": now.strftime("%Y-%m-%d"),
            "signature": signature_b64
        }

    @classmethod
    def transfer_license(
        cls,
        existing_license: Dict[str, Any],
        new_machine_fingerprint: str,
        private_key: Optional[rsa.RSAPrivateKey] = None
    ) -> Dict[str, Any]:
        """
        Permite transferir una licencia vigente a un nuevo ordenador re-firmando el payload.
        """
        pkey = private_key or cls.get_master_private_key()
        holder = existing_license.get("holder", "Cliente Alfonso")
        client_id = existing_license.get("client_id", "default")
        expires_at = existing_license.get("expires_at", datetime.now().strftime("%Y-%m-%d"))

        payload = {
            "license_type": existing_license.get("license_type", "premium"),
            "holder": holder,
            "expires_at": expires_at,
            "machine_fingerprint": new_machine_fingerprint
        }

        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = pkey.sign(
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature).decode("utf-8")

        return {
            "license_type": payload["license_type"],
            "holder": holder,
            "client_id": client_id,
            "expires_at": expires_at,
            "machine_fingerprint": new_machine_fingerprint,
            "transferred_at": datetime.now().strftime("%Y-%m-%d"),
            "signature": signature_b64
        }
