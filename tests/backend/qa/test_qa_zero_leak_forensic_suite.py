import pytest
import re
from app.infrastructure.logging.filters import GDPRSanitizingFilter

def test_qa_forensic_sanitization_patterns():
    filter_ = GDPRSanitizingFilter()

    sensitive_samples = [
        ("NIF persona física", "12345678Z", "12******Z"),
        ("IBAN bancario", "ES6621000418401234567891", "ES66****************7891"),
        ("Email corporativo", "usuario.prueba@empresa.es", "us***@empresa.es"),
    ]

    for label, raw, expected_obfuscated in sensitive_samples:
        sanitized = filter_._sanitize(f"Texto con {raw} incluido.")
        assert raw not in sanitized, f"Fuga de {label}: {sanitized}"
