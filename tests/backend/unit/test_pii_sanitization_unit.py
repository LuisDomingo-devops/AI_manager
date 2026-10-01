"""
Test Unitario para Sanitización y Ofuscación de PII (User Story 6: RGPD y Privacidad).
Valida que NIFs, IBANs, correos y datos financieros sensibles queden ofuscados en logs y auditoría.
"""

import pytest
from app.infrastructure.monitoring.audit_ledger_service import AuditLedgerService


def test_pii_sanitization_nif_and_iban():
    """Valida la ofuscación de NIFs e IBANs en textos y estructuras de datos de auditoría."""
    service = AuditLedgerService()
    
    raw_payload = {
        "client_nif": "12345678Z",
        "company_cif": "B12345674",
        "bank_iban": "ES9121000418450200051332",
        "email": "contacto@autonomo.es",
        "gross_salary": 2500.50
    }
    
    sanitized = service.sanitize_payload(raw_payload)
    
    # Verificar ofuscación de NIF
    assert "12345678Z" not in str(sanitized)
    assert "123***" in sanitized["client_nif"] or "***78Z" in sanitized["client_nif"] or "*****" in sanitized["client_nif"]
    
    # Verificar ofuscación de IBAN
    assert "ES9121000418450200051332" not in str(sanitized)
    assert "ES91" in sanitized["bank_iban"]
    assert "332" in sanitized["bank_iban"]
    assert "***" in sanitized["bank_iban"]
    
    # Verificar ofuscación de Email
    assert "contacto@autonomo.es" not in str(sanitized)
    assert "@autonomo.es" in sanitized["email"]


def test_pii_sanitization_free_text():
    """Valida que textos libres en descripciones de logs eliminen NIFs completos."""
    service = AuditLedgerService()
    text = "Pago realizado por el cliente con DNI 12345678Z a la cuenta ES9121000418450200051332."
    sanitized_text = service.sanitize_text(text)
    
    assert "12345678Z" not in sanitized_text
    assert "ES9121000418450200051332" not in sanitized_text
