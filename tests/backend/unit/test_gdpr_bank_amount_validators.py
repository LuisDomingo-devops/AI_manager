import pytest
from app.utils.fiscal_validators import (
    validate_iban,
    validate_spanish_ccc,
    extract_amounts_with_context
)

def test_valid_spanish_iban():
    # IBAN español válido con ISO 7064 mod 97-10
    assert validate_iban("ES6621000418401234567891") is True
    assert validate_iban("ES66 2100 0418 40 1234567891") is True

def test_invalid_spanish_iban():
    # Dígitos de control de IBAN alterados
    assert validate_iban("ES0021000418401234567891") is False
    # Longitud incorrecta
    assert validate_iban("ES912100041840123456789") is False

def test_international_iban():
    # IBAN francés válido
    assert validate_iban("FR1420041010050500013M02606") is True

def test_extract_amounts_not_years():
    text = "En el ejercicio 2026 se pagaron 1.500,50 € y 300 EUR por la factura FAC-2026-99."
    amounts = extract_amounts_with_context(text)
    extracted_strings = [a[0] for a in amounts]
    assert any("1.500,50" in s for s in extracted_strings)
    assert any("300 EUR" in s for s in extracted_strings)
    # Comprobar que el año 2026 NO se clasifica como importe monetario
    for amt, raw in amounts:
        assert "2026" != raw.strip()
