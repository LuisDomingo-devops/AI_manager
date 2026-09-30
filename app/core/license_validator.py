import os
import json
import base64
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives import hashes, serialization

from app.utils.license_validator import (
    PUBLIC_KEY_PEM as DEFAULT_PUBLIC_KEY_PEM,
    LICENSE_PATH as DEFAULT_LICENSE_PATH,
    CLOCK_INTEGRITY_PATH as DEFAULT_CLOCK_PATH,
    DEFAULT_GRACE_PERIOD_DAYS,
    LicenseStatusResult,
    get_machine_fingerprint,
    check_clock_integrity,
    generate_signed_license,
)

class OfflineLicenseValidator:
    """
    Validador criptográfico RSA de licencias locales offline.
    Permite validar firmas asimétricas sin conexión a internet ni dependencias SaaS.
    """
    def __init__(
        self,
        public_key_pem: Optional[bytes] = None,
        license_path: Optional[Path] = None,
        clock_path: Optional[Path] = None,
    ):
        self.public_key_pem = public_key_pem or DEFAULT_PUBLIC_KEY_PEM
        self.license_path = license_path or DEFAULT_LICENSE_PATH
        self.clock_path = clock_path or DEFAULT_CLOCK_PATH

    def validate(
        self,
        current_dt: Optional[datetime] = None,
        override_machine_fingerprint: Optional[str] = None
    ) -> LicenseStatusResult:
        now = current_dt or datetime.now()
        local_fp = override_machine_fingerprint or get_machine_fingerprint()

        if not self.license_path.exists():
            return LicenseStatusResult(
                status="missing",
                is_operational=False,
                machine_fingerprint=local_fp,
                message="No se ha encontrado el archivo de licencia local."
            )

        try:
            content = self.license_path.read_text(encoding="utf-8")
            license_data = json.loads(content)
        except Exception as e:
            return LicenseStatusResult(
                status="invalid_signature",
                is_operational=False,
                machine_fingerprint=local_fp,
                message=f"Archivo de licencia corrupto o no válido: {e}"
            )

        raw_type = str(license_data.get("license_type", "")).strip().lower()
        payload = {
            "license_type": license_data.get("license_type"),
            "holder": license_data.get("holder"),
            "expires_at": license_data.get("expires_at"),
        }
        if "machine_fingerprint" in license_data and license_data["machine_fingerprint"]:
            payload["machine_fingerprint"] = license_data["machine_fingerprint"]

        signature_b64 = license_data.get("signature")
        if not signature_b64:
            return LicenseStatusResult(
                status="invalid_signature",
                is_operational=False,
                machine_fingerprint=local_fp,
                message="Licencia sin firma digital."
            )

        # Verificación criptográfica RSA
        try:
            payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
            signature = base64.b64decode(signature_b64.encode("utf-8"))
            public_key = serialization.load_pem_public_key(self.public_key_pem)

            public_key.verify(
                signature,
                payload_bytes,
                padding.PKCS1v15(),
                hashes.SHA256()
            )
        except Exception:
            return LicenseStatusResult(
                status="invalid_signature",
                is_operational=False,
                machine_fingerprint=local_fp,
                message="Firma criptográfica inválida o manipulada."
            )

        # Machine binding
        license_fp = payload.get("machine_fingerprint")
        if license_fp and license_fp != local_fp:
            return LicenseStatusResult(
                status="machine_mismatch",
                is_operational=False,
                holder=payload.get("holder"),
                license_type=raw_type,
                tier=raw_type,
                machine_fingerprint=local_fp,
                expires_at=payload.get("expires_at"),
                message="La licencia no coincide con el hardware de esta máquina."
            )

        # Fecha y período de gracia
        expires_at_str = payload.get("expires_at")
        if not expires_at_str:
            return LicenseStatusResult(
                status="invalid_format",
                is_operational=False,
                machine_fingerprint=local_fp,
                message="Fecha de expiración no especificada."
            )

        try:
            exp_date = datetime.strptime(expires_at_str, "%Y-%m-%d").date()
        except ValueError:
            return LicenseStatusResult(
                status="invalid_format",
                is_operational=False,
                machine_fingerprint=local_fp,
                message="Formato de fecha inválido."
            )

        today = now.date()
        if today <= exp_date:
            days_left = (exp_date - today).days
            return LicenseStatusResult(
                status="active",
                is_operational=True,
                holder=payload.get("holder"),
                client_id=license_data.get("client_id"),
                license_type=raw_type,
                tier=raw_type,
                expires_at=expires_at_str,
                machine_fingerprint=local_fp,
                days_until_expiration=days_left,
                grace_days_remaining=DEFAULT_GRACE_PERIOD_DAYS,
                message="Licencia activa y operativa."
            )

        days_overdue = (today - exp_date).days
        if days_overdue <= DEFAULT_GRACE_PERIOD_DAYS:
            grace_left = DEFAULT_GRACE_PERIOD_DAYS - days_overdue
            return LicenseStatusResult(
                status="grace_period",
                is_operational=True,
                holder=payload.get("holder"),
                client_id=license_data.get("client_id"),
                license_type=raw_type,
                tier=raw_type,
                expires_at=expires_at_str,
                machine_fingerprint=local_fp,
                days_until_expiration=0,
                grace_days_remaining=grace_left,
                message="Licencia en período de gracia."
            )

        return LicenseStatusResult(
            status="expired",
            is_operational=False,
            holder=payload.get("holder"),
            client_id=license_data.get("client_id"),
            license_type=raw_type,
            tier=raw_type,
            expires_at=expires_at_str,
            machine_fingerprint=local_fp,
            days_until_expiration=0,
            grace_days_remaining=0,
            message="Licencia expirada."
        )
