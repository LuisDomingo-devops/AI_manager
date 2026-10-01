"""
Servicio de Registro de Auditoría y Sanitización de PII (RGPD).
Ofusca datos personales identificables (NIFs, IBANs, correos) en logs y registros de auditoría.
"""

import re
from typing import Dict, Any, Union


class AuditLedgerService:
    """Ofusca y protege la privacidad de los datos personales en la capa de auditoría."""

    # Regex para NIF/NIE/CIF español
    NIF_PATTERN = re.compile(r'\b([A-HJ-NP-SUVWXYZ\d]\d{7}[A-HJ-NP-SUVWXYZ\d])\b', re.IGNORECASE)
    # Regex para IBAN español
    IBAN_PATTERN = re.compile(r'\b(ES\d{2})[\s-]?(\d{4})[\s-]?(\d{4})[\s-]?(\d{2})[\s-]?(\d{10})\b', re.IGNORECASE)
    # Regex para correo electrónico
    EMAIL_PATTERN = re.compile(r'\b([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b')

    @classmethod
    def mask_nif(cls, nif: str) -> str:
        """Ofusca el cuerpo central del NIF/NIE: 12345678Z -> 123***78Z."""
        clean = nif.strip()
        if len(clean) >= 9:
            return f"{clean[:3]}***{clean[-2:]}"
        return "*****"

    @classmethod
    def mask_iban(cls, iban: str) -> str:
        """Ofusca la cuenta bancaria manteniendo país y últimos 3 dígitos: ES91****************332."""
        clean = iban.replace(" ", "").replace("-", "").strip()
        if len(clean) >= 24:
            return f"{clean[:4]}{'*' * 17}{clean[-3:]}"
        return f"{clean[:2]}****************{clean[-2:]}" if len(clean) >= 4 else "****************"

    @classmethod
    def mask_email(cls, email: str) -> str:
        """Ofusca el nombre de usuario de la dirección de correo: usuario@dominio.com -> u***o@dominio.com."""
        parts = email.split("@")
        if len(parts) == 2:
            user, domain = parts
            if len(user) > 2:
                masked_user = f"{user[0]}***{user[-1]}"
            else:
                masked_user = "***"
            return f"{masked_user}@{domain}"
        return "***@***"

    def sanitize_text(self, text: str) -> str:
        """Ofusca NIFs, IBANs y correos en un bloque de texto libre."""
        if not text:
            return ""

        # Reemplazar IBANs primero (más largos)
        text = self.IBAN_PATTERN.sub(lambda m: self.mask_iban(m.group(0)), text)
        # Reemplazar correos
        text = self.EMAIL_PATTERN.sub(lambda m: self.mask_email(m.group(0)), text)
        # Reemplazar NIFs
        text = self.NIF_PATTERN.sub(lambda m: self.mask_nif(m.group(0)), text)

        return text

    def sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Recorre recursivamente un diccionario u objeto JSON y ofusca campos PII."""
        sanitized = {}
        for k, v in payload.items():
            key_lower = k.lower()
            if isinstance(v, str):
                if any(term in key_lower for term in ("nif", "cif", "nie", "tax_id")):
                    sanitized[k] = self.mask_nif(v)
                elif any(term in key_lower for term in ("iban", "account_number", "bank_account")):
                    sanitized[k] = self.mask_iban(v)
                elif any(term in key_lower for term in ("email", "correo")):
                    sanitized[k] = self.mask_email(v)
                else:
                    sanitized[k] = self.sanitize_text(v)
            elif isinstance(v, dict):
                sanitized[k] = self.sanitize_payload(v)
            elif isinstance(v, list):
                sanitized[k] = [
                    self.sanitize_payload(item) if isinstance(item, dict) else (
                        self.sanitize_text(item) if isinstance(item, str) else item
                    )
                    for item in v
                ]
            else:
                sanitized[k] = v
        return sanitized
