"""
Tests unitarios para el parser universal de extractos bancarios en CSV.
Valida la autodetección de delimitadores, formatos numéricos españoles (1.234,56 €) y cuadre con Decimal.
"""
import pytest
from decimal import Decimal
from app.domain.services.bank_csv_parser import BankCsvParser
from app.domain.schemas import BankStatementDTO
from app.domain.exceptions import BankStatementDiscrepancyError


def test_bank_csv_parser_spanish_semicolon_format():
    """Valida el parseo de CSV español con punto y coma y números con coma decimal."""
    parser = BankCsvParser()

    csv_content = """FECHA OPERACIÓN;FECHA VALOR;CONCEPTO;IMPORTE;SALDO
01/02/2026;01/02/2026;SALDO INICIAL;;5.000,00 €
02/02/2026;02/02/2026;TRANSFERENCIA CLIENTE ACME;1.210,00 €;6.210,00 €
03/02/2026;03/02/2026;RECIBO TELEFONICA;-150,50 €;6.059,50 €
04/02/2026;04/02/2026;COMISION MANTENIMIENTO TPV;-12,00 €;6.047,50 €
"""
    statement = parser.parse(csv_content, account_iban="ES9121000418450200051332")

    assert isinstance(statement, BankStatementDTO)
    assert statement.initial_balance == Decimal("5000.00")
    assert statement.final_balance == Decimal("6047.50")
    assert len(statement.entries) == 3

    assert statement.entries[0].amount == Decimal("1210.00")
    assert statement.entries[0].operation_date == "2026-02-02"
    assert "ACME" in statement.entries[0].concept

    assert statement.entries[1].amount == Decimal("-150.50")
    assert statement.entries[1].operation_date == "2026-02-03"

    assert statement.entries[2].amount == Decimal("-12.00")
    assert statement.entries[2].balance_after == Decimal("6047.50")


def test_bank_csv_parser_comma_separated_with_decimal_dots():
    """Valida extractos bancarios en CSV con coma y puntos decimales (Wise / Revolut)."""
    parser = BankCsvParser()

    csv_content = """Date,Value Date,Description,Amount,Balance
2026-03-01,2026-03-01,Opening balance,,1000.00
2026-03-05,2026-03-05,Invoice payment 2026-0044,250.00,1250.00
2026-03-06,2026-03-06,AWS EMEA Hosting,-80.00,1170.00
"""
    statement = parser.parse(csv_content, account_iban="ES9100491500051234567892")

    assert statement.initial_balance == Decimal("1000.00")
    assert statement.final_balance == Decimal("1170.00")
    assert len(statement.entries) == 2
    assert statement.entries[0].amount == Decimal("250.00")
    assert statement.entries[1].amount == Decimal("-80.00")


def test_bank_csv_parser_detects_discrepancy():
    """Valida que un CSV con saltos o saldos descuadrados lanza BankStatementDiscrepancyError."""
    parser = BankCsvParser()

    # Saldo inicial 1000, movimiento +200, pero saldo final declarado en la última línea es 1500 (descuadre de 300)
    csv_content = """FECHA;CONCEPTO;IMPORTE;SALDO
01/01/2026;SALDO INICIAL;;1000,00
02/01/2026;COBRO FACTURA;200,00;1500,00
"""
    with pytest.raises(BankStatementDiscrepancyError) as exc_info:
        parser.parse(csv_content)

    err = exc_info.value
    assert err.initial_balance == Decimal("1000.00")
    assert err.final_balance == Decimal("1500.00")
    assert err.calculated_final == Decimal("1200.00")
