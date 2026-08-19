import pytest
from app.domain.services.fiscal_validator import (
    validate_spanish_id,
    validate_arithmetic_consistency,
    validate_invoice_for_sif,
    FiscalValidationResult
)


def test_validate_spanish_id_dni():
    # DNI Válidos (8 dígitos + letra módulo 23)
    # 12345678Z -> 12345678 % 23 = 14 -> Z
    assert validate_spanish_id("12345678Z")[0] is True
    # 00000000T -> 0 % 23 = 0 -> T
    assert validate_spanish_id("00000000T")[0] is True

    # DNI Letra incorrecta
    is_valid, msg = validate_spanish_id("12345678A")
    assert is_valid is False
    assert "Letra de NIF incorrecta" in msg

    # Longitud incorrecta
    assert validate_spanish_id("1234567Z")[0] is False


def test_validate_spanish_id_nie():
    # NIE Válido: X1234567L (X -> 01234567 % 23 = 11 -> L)
    # 1234567 % 23 = 11 -> L
    assert validate_spanish_id("X1234567L")[0] is True
    # Y1234567X (Y -> 11234567 % 23 = 10 -> X)
    assert validate_spanish_id("Y1234567X")[0] is True

    # NIE Letra incorrecta
    assert validate_spanish_id("X1234567A")[0] is False


def test_validate_spanish_id_cif():
    # CIF Empresa S.L. tipo B: B12345678 -> calculamos
    # CIF con dígito numérico o letra
    # CIF A58818501 (válido estándar)
    # Suma pares: 8+1+5=14; impares: 5*2=1(0+1)+8*2=7(1+6)+8*2=7(1+6)+0*2=0 -> 1+7+7+0=15; total=29 -> control=(10-9)=1
    assert validate_spanish_id("A58818501")[0] is True

    # CIF inválido
    assert validate_spanish_id("A58818509")[0] is False


def test_validate_arithmetic_consistency():
    # Factura cuadrada 100€ base, 21% IVA -> 21€ IVA, 121€ Total
    valid, errors = validate_arithmetic_consistency(
        base_imponible=100.0,
        iva_amount=21.0,
        total_amount=121.0,
        iva_rate=21.0
    )
    assert valid is True
    assert len(errors) == 0

    # Factura con retención IRPF (100€ base, 21% IVA, 15% IRPF -> 100 + 21 - 15 = 106€)
    valid_irpf, errors_irpf = validate_arithmetic_consistency(
        base_imponible=100.0,
        iva_amount=21.0,
        total_amount=106.0,
        iva_rate=21.0,
        irpf_amount=15.0,
        irpf_rate=15.0
    )
    assert valid_irpf is True
    assert len(errors_irpf) == 0

    # Descuadre en cuota de IVA
    invalid_iva, errs_iva = validate_arithmetic_consistency(
        base_imponible=100.0,
        iva_amount=25.0,  # Debería ser 21.0
        total_amount=125.0,
        iva_rate=21.0
    )
    assert invalid_iva is False
    assert any("Descuadre en cuota de IVA" in e for e in errs_iva)

    # Descuadre en Total
    invalid_total, errs_tot = validate_arithmetic_consistency(
        base_imponible=100.0,
        iva_amount=21.0,
        total_amount=120.0,  # Debería ser 121.0
        iva_rate=21.0
    )
    assert invalid_total is False
    assert any("Descuadre en importe total" in e for e in errs_tot)


def test_validate_invoice_for_sif_valid():
    valid_invoice = {
        "invoice_number": "F2026-001",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "X1234567L",
        "base_imponible": 500.0,
        "iva_amount": 105.0,
        "total_amount": 605.0,
        "iva_rate": 21.0,
        "tipo_factura": "F1"
    }
    result = validate_invoice_for_sif(valid_invoice)
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_invoice_for_sif_invalid_nif():
    invalid_invoice = {
        "invoice_number": "F2026-002",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678A",  # NIF con letra errónea
        "receiver_nif": "00000000T",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0,
        "iva_rate": 21.0
    }
    result = validate_invoice_for_sif(invalid_invoice)
    assert result.is_valid is False
    assert any("no válido" in e for e in result.errors)


def test_validate_invoice_for_sif_invalid_tax_rate():
    invalid_tax_invoice = {
        "invoice_number": "F2026-003",
        "date_of_issue": "19-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "00000000T",
        "base_imponible": 100.0,
        "iva_amount": 17.0,
        "total_amount": 117.0,
        "iva_rate": 17.0  # 17% no es un tipo impositivo legal en España
    }
    result = validate_invoice_for_sif(invalid_tax_invoice)
    assert result.is_valid is False
    assert any("no es un tipo impositivo legal" in e for e in result.errors)
