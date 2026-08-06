import os
import json
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization

# Clave pública RSA por defecto para validar firmas de licencias de Alfonso Autónomo
# En producción, esto corresponde a la clave privada en posesión de Alfonso S.L.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzqXzR8F3X5h1S8jD1Y7g
Vb5Z4y3sX4bH26mZ+8W4Kj4Y2Xk1CjX4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S
1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1
X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X
4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4
K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K2+S1X4K
wIDAQAB
-----END PUBLIC KEY-----"""

LICENSE_PATH = Path(__file__).resolve().parents[2] / "data" / "license.lic"

def is_premium_license_valid() -> bool:
    """
    Verifica criptográficamente si la licencia premium local es válida.
    Comprueba firma, fecha de expiración y tipo de licencia.
    """
    # 1. Fallback rápido de desarrollo: Si se inyecta una clave de bypass válida de desarrollo, habilitarla temporalmente
    dev_bypass = os.getenv("ALFONSO_DEV_PREMIUM_BYPASS")
    if dev_bypass == "AlfonsoDevelopmentToken2026!":
        return True

    # 2. Si no hay archivo de licencia, no es premium
    if not LICENSE_PATH.exists():
        return False

    try:
        # Cargar archivo de licencia
        license_data = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
        
        # Extraer metadatos y firma
        payload = {
            "license_type": license_data.get("license_type"),
            "holder": license_data.get("holder"),
            "expires_at": license_data.get("expires_at")
        }
        signature_b64 = license_data.get("signature")
        if not signature_b64:
            return False

        # Serializar payload de forma determinista para la verificación
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        signature = base64.b64decode(signature_b64.encode("utf-8"))

        # Cargar clave pública
        public_key = serialization.load_pem_public_key(PUBLIC_KEY_PEM)

        # Verificar la firma criptográfica RSA-SHA256
        public_key.verify(
            signature,
            payload_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        # Comprobar expiración y tipo de licencia
        from datetime import datetime
        expires_at_str = payload.get("expires_at")
        if expires_at_str:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d")
            if expires_at < datetime.now():
                return False

        return payload.get("license_type") == "premium"

    except Exception:
        # Cualquier alteración del archivo, firma inválida o error en el formato invalida la licencia
        return False
