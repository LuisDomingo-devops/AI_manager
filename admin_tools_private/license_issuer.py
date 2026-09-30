import os
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization

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
        """Carga y valida estrictamente la clave privada maestra de firma RSA."""
        pem_bytes = custom_pem or os.getenv("ALFONSO_MASTER_PRIVATE_KEY_PEM", "").encode("utf-8")
        if not pem_bytes or not pem_bytes.strip():
            raise RuntimeError("No se ha configurado una clave privada maestra RSA válida para emisión de licencias")
        
        try:
            key = serialization.load_pem_private_key(pem_bytes, password=None)
            if not isinstance(key, rsa.RSAPrivateKey):
                raise ValueError("Clave privada maestra RSA inválida o corrupta: no es de tipo RSA")
            return key
        except Exception as e:
            raise ValueError(f"Clave privada maestra RSA inválida o corrupta: {str(e)}") from e

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
        if not isinstance(pkey, rsa.RSAPrivateKey):
            raise ValueError("Clave privada maestra RSA inválida o corrupta")
            
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
        if not isinstance(pkey, rsa.RSAPrivateKey):
            raise ValueError("Clave privada maestra RSA inválida o corrupta")

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
        if not isinstance(pkey, rsa.RSAPrivateKey):
            raise ValueError("Clave privada maestra RSA inválida o corrupta")

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
