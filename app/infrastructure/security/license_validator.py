"""
Adaptador de infraestructura para validación de licencias criptográficas offline.
Utiliza clave pública embebida y algoritmos RSA PKCS#1 v1.5 / PSS sin exponer claves privadas.
"""

from pathlib import Path
from typing import Optional, Dict, Any
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes, serialization
from app.core.license_validator import (
    OfflineLicenseValidator,
    DEFAULT_PUBLIC_KEY_PEM,
    DEFAULT_LICENSE_PATH,
    DEFAULT_CLOCK_PATH,
    LicenseStatusResult,
    get_machine_fingerprint,
    check_clock_integrity,
    generate_signed_license,
)


class LicenseValidator:
    """
    Validador de licencias para el entorno de cliente.
    Verifica criptográficamente firmas digitales sin necesidad de claves privadas ni conexión remota.
    """
    def __init__(self, public_key_pem: Optional[bytes] = None):
        self.public_key_pem = public_key_pem or DEFAULT_PUBLIC_KEY_PEM
        # Cargar clave pública RSA
        try:
            self.public_key = serialization.load_pem_public_key(self.public_key_pem)
        except Exception:
            self.public_key = None

    def validate_license_offline(self, license_token: str) -> Dict[str, Any]:
        """
        Valida un token de licencia en formato compacto (payload.signature o JWT).
        Retorna {"valid": True, ...} o {"valid": False, "error": ...}
        """
        if not license_token or "." not in license_token:
            return {"valid": False, "error": "Formato de licencia inválido."}

        parts = license_token.split(".")
        if len(parts) < 2:
            return {"valid": False, "error": "Estructura de firma inválida."}

        payload_b64 = parts[0]
        sig_b64 = parts[-1]

        import base64
        try:
            # Padding seguro para base64
            sig_padded = sig_b64 + "=" * (-len(sig_b64) % 4)
            signature = base64.urlsafe_b64decode(sig_padded.encode())
            payload_bytes = payload_b64.encode()
            
            if self.public_key is None:
                return {"valid": False, "error": "Clave pública no inicializada."}

            self.public_key.verify(
                signature,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
            return {"valid": True, "message": "Licencia criptográfica válida."}
        except Exception as e:
            return {"valid": False, "error": f"Firma digital de licencia inválida: {str(e)}"}


__all__ = [
    "LicenseValidator",
    "OfflineLicenseValidator",
    "DEFAULT_PUBLIC_KEY_PEM",
    "DEFAULT_LICENSE_PATH",
    "DEFAULT_CLOCK_PATH",
    "LicenseStatusResult",
    "get_machine_fingerprint",
    "check_clock_integrity",
    "generate_signed_license",
]
