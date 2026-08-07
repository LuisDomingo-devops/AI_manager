import os
import json
import base64
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization

# Clave pública RSA por defecto para validar firmas de licencias de Alfonso Autónomo
# En producción, esto corresponde a la clave privada en posesión de Alfonso S.L.
PUBLIC_KEY_PEM = b"""-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA4vxqcQyYeJuz3wEr1IRZ
QJ70ygRTchcOqNroZYZRSEM0ngBLl8S/J24Vy0Me/j4mjmWJo75NO7UsDXCTll9E
GBDD+PEYoSsIIre1l6RNqI31iBTetaIcbjKiQ9P7ExYWflhPH8N0Xm5ESPktQw7W
Q8NJHdR1/ovUdEC3EC1hjac3HcNtEgcpwc3HZtIds7+QuQTFaHxyMFCpovUnmddY
sEVP8t0jwc9TiXc3BcnCIqJyx3ymvIyEM23wMrl1mpG07PQkn0jO0sY8ThwyXqM0
Oum6lYfIVVrzBeciDHky82Q60xyqpaArkXRu2zqBnXaa0/FHzRAuGUn38NN58W4x
lwIDAQAB
-----END PUBLIC KEY-----"""

LICENSE_PATH = Path(__file__).resolve().parents[2] / "data" / "license.lic"

def is_premium_license_valid() -> bool:
    """
    Verifica criptográficamente si la licencia premium local es válida.
    Comprueba firma, fecha de expiración y tipo de licencia.
    """
    # 1. Fallback rápido de desarrollo: Permitido ÚNICAMENTE en entorno de test automatizado (pytest)
    is_testing = os.getenv("ALFONSO_IS_TESTING") == "True" or os.getenv("PYTEST_CURRENT_TEST") is not None
    if is_testing:
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
