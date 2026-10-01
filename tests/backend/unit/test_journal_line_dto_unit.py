"""Tests Unitarios para JournalLineDTO y RecordJournalEntryCommand tipado con Decimal.
Cumple con la especificación 026 y la recomendación I1.
"""
from decimal import Decimal
import pytest
from pydantic import ValidationError
from datetime import date

from app.domain.accounting.ports import JournalLineDTO, RecordJournalEntryCommand


def test_journal_line_dto_valid_creation():
    """Valida la creación correcta de JournalLineDTO con cuantización Decimal."""
    line = JournalLineDTO(
        account_code="4300000",
        concept="Factura cliente",
        debit="1210.555",  # Debe redondear a 1210.56
        credit=0
    )
    assert line.account_code == "4300000"
    assert line.concept == "Factura cliente"
    assert line.debit == Decimal("1210.56")
    assert line.credit == Decimal("0.00")


def test_journal_line_dto_supports_account_alias():
    """Valida que acepta 'account' como alias de 'account_code' para compatibilidad."""
    line = JournalLineDTO.model_validate({
        "account": "700000",
        "concept": "Venta mercaderías",
        "debit": 0,
        "credit": 1000.00
    })
    assert line.account_code == "700000"
    assert line.credit == Decimal("1000.00")


def test_journal_line_dto_invalid_account_code_raises_validation_error():
    """Valida que rechaza códigos de cuenta que no cumplan el patrón PGC de 3 a 7 dígitos."""
    # Menos de 3 dígitos
    with pytest.raises(ValidationError):
        JournalLineDTO(account_code="43", concept="Test", debit=10, credit=0)

    # Más de 10 dígitos
    with pytest.raises(ValidationError):
        JournalLineDTO(account_code="43000000001", concept="Test", debit=10, credit=0)

    # Caracteres no numéricos
    with pytest.raises(ValidationError):
        JournalLineDTO(account_code="43000A", concept="Test", debit=10, credit=0)


def test_journal_line_dto_negative_amount_rejected():
    """Valida que no se permiten importes negativos al Debe o Haber."""
    with pytest.raises(ValidationError):
        JournalLineDTO(account_code="572000", concept="Banco", debit=-50, credit=0)


def test_record_journal_entry_command_with_typed_lines():
    """Valida que RecordJournalEntryCommand parsea y tipa la lista de líneas como JournalLineDTO."""
    cmd = RecordJournalEntryCommand(
        tenant_id="tenant_test",
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Asiento de apertura",
        lines=[
            {"account_code": "572000", "concept": "Tesorería", "debit": 1000, "credit": 0},
            {"account_code": "100000", "concept": "Capital", "debit": 0, "credit": 1000}
        ]
    )
    assert len(cmd.lines) == 2
    assert isinstance(cmd.lines[0], JournalLineDTO)
    assert isinstance(cmd.lines[1], JournalLineDTO)
    assert cmd.lines[0].debit == Decimal("1000.00")
    assert cmd.lines[1].credit == Decimal("1000.00")
