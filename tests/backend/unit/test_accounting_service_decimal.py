"""Tests Unitarios para AccountingService y Cuadre Decimal Estricto (T006 - TDD).
Valida tolerancia cero en descuadre contable y aritmética Decimal (Spec 026 - US1).
"""
from datetime import date
from decimal import Decimal
import pytest
from pydantic import ValidationError

from app.domain.accounting.ports import JournalLineDTO, RecordJournalEntryCommand
from app.domain.accounting.services import AccountingService
from app.domain.exceptions import UnbalancedJournalEntryError


def test_balanced_journal_entry_succeeds_with_decimal_precision(monkeypatch):
    """Valida que un asiento exactamente cuadrado es procesado con éxito."""
    service = AccountingService()
    
    # Mockeamos legal_write_transaction para probar la lógica de dominio en test unitario
    recorded_commands = []
    
    class FakeCursor:
        def execute(self, sql, params=None):
            pass
        def fetchone(self):
            return (0,)
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    class FakeContext:
        def __enter__(self):
            return FakeConn()
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr("app.domain.accounting.services.legal_write_transaction", lambda client_id: FakeContext())

    cmd = RecordJournalEntryCommand(
        tenant_id="tenant_unit",
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Asiento de ventas con céntimos",
        lines=[
            JournalLineDTO(account_code="430000", concept="Cliente", debit=Decimal("1210.55"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Venta", debit=Decimal("0.00"), credit=Decimal("1000.45")),
            JournalLineDTO(account_code="477000", concept="IVA", debit=Decimal("0.00"), credit=Decimal("210.10")),
        ]
    )

    entry = service.record_entry(cmd)
    assert entry.is_balanced is True
    assert entry.entry_number == 1


def test_unbalanced_journal_entry_by_one_cent_raises_unbalanced_error():
    """Valida que un descuadre de exactamente 1 céntimo lanza UnbalancedJournalEntryError."""
    service = AccountingService()

    cmd = RecordJournalEntryCommand(
        tenant_id="tenant_unit",
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Asiento descuadrado por 1 céntimo",
        lines=[
            JournalLineDTO(account_code="430000", concept="Cliente", debit=Decimal("100.01"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Venta", debit=Decimal("0.00"), credit=Decimal("100.00")),
        ]
    )

    with pytest.raises(UnbalancedJournalEntryError) as exc_info:
        service.record_entry(cmd)

    assert "total Debe (100.01) != total Haber (100.00)" in str(exc_info.value)
    assert exc_info.value.details["difference"] == "0.01"


def test_record_journal_entry_command_requires_at_least_two_lines():
    """Valida que un asiento no puede registrarse con menos de 2 líneas."""
    with pytest.raises(ValidationError):
        RecordJournalEntryCommand(
            tenant_id="tenant_unit",
            entry_date=date(2026, 10, 1),
            fiscal_year=2026,
            concept="Asiento unilateral ilícito",
            lines=[
                JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("100.00"), credit=Decimal("0.00"))
            ]
        )


def test_record_entry_in_closed_fiscal_year_raises_fiscal_year_closed_error(monkeypatch):
    """Valida que intentar registrar un asiento en un ejercicio cerrado lanza FiscalYearClosedError (T010)."""
    from app.domain.exceptions import FiscalYearClosedError

    service = AccountingService()
    monkeypatch.setattr(service, "is_fiscal_year_closed", lambda tenant_id, fiscal_year: True)

    cmd = RecordJournalEntryCommand(
        tenant_id="tenant_unit",
        entry_date=date(2025, 12, 31),
        fiscal_year=2025,
        concept="Asiento en ejercicio cerrado",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Venta", debit=Decimal("0.00"), credit=Decimal("100.00")),
        ]
    )

    with pytest.raises(FiscalYearClosedError) as exc_info:
        service.record_entry(cmd)

    assert "cerrado e inmutable" in str(exc_info.value)


def test_post_rectification_sales_invoice_generates_correct_pgc_entry(monkeypatch):
    """Valida la generación de contraasiento para abono/rectificativa emitida (708/477 contra 430) (T014)."""
    from app.domain.accounting.ports import PostRectificationInvoiceCommand

    service = AccountingService()
    captured_commands = []
    monkeypatch.setattr(service, "record_entry", lambda cmd: captured_commands.append(cmd) or cmd)

    cmd = PostRectificationInvoiceCommand(
        tenant_id="tenant_unit",
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        invoice_number="R2026-0001",
        rectified_invoice_number="F2026-0001",
        taxable_base=Decimal("1000.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("210.00"),
        total_amount=Decimal("1210.00"),
        third_party_account="430000",
        is_sales=True
    )

    service.post_rectification_entry(cmd)

    assert len(captured_commands) == 1
    recorded = captured_commands[0]
    assert recorded.concept == "Factura rectificativa ventas R2026-0001 (rectifica F2026-0001)"
    assert len(recorded.lines) == 3
    # Debe 708 (1000.00), Debe 477 (210.00), Haber 430 (1210.00)
    lines_map = {l.account_code: (l.debit, l.credit) for l in recorded.lines}
    assert lines_map["708000"] == (Decimal("1000.00"), Decimal("0.00"))
    assert lines_map["477000"] == (Decimal("210.00"), Decimal("0.00"))
    assert lines_map["430000"] == (Decimal("0.00"), Decimal("1210.00"))


def test_post_rectification_purchase_invoice_generates_correct_pgc_entry(monkeypatch):
    """Valida la generación de contraasiento para abono/rectificativa recibida (400 contra 608/472) (T014)."""
    from app.domain.accounting.ports import PostRectificationInvoiceCommand

    service = AccountingService()
    captured_commands = []
    monkeypatch.setattr(service, "record_entry", lambda cmd: captured_commands.append(cmd) or cmd)

    cmd = PostRectificationInvoiceCommand(
        tenant_id="tenant_unit",
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        invoice_number="ABONO-PROV-01",
        rectified_invoice_number="FAC-PROV-01",
        taxable_base=Decimal("500.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("105.00"),
        total_amount=Decimal("605.00"),
        third_party_account="400000",
        is_sales=False
    )

    service.post_rectification_entry(cmd)

    assert len(captured_commands) == 1
    recorded = captured_commands[0]
    assert recorded.concept == "Factura rectificativa compras ABONO-PROV-01 (rectifica FAC-PROV-01)"
    assert len(recorded.lines) == 3
    # Debe 400 (605.00), Haber 608 (500.00), Haber 472 (105.00)
    lines_map = {l.account_code: (l.debit, l.credit) for l in recorded.lines}
    assert lines_map["400000"] == (Decimal("605.00"), Decimal("0.00"))
    assert lines_map["608000"] == (Decimal("0.00"), Decimal("500.00"))
    assert lines_map["472000"] == (Decimal("0.00"), Decimal("105.00"))


def test_get_ledger_calculates_progressive_decimal_balance(monkeypatch):
    """Valida que get_ledger calcule el saldo progresivo exacto en tipo Decimal (T018)."""
    service = AccountingService()

    class FakeCursor:
        def execute(self, query, params):
            pass
        def fetchall(self):
            # entry_number, entry_date, concept, debit, credit
            return [
                (1, "2026-01-10", "Apertura / Cobro", "1000.00", "0.00"),
                (2, "2026-02-15", "Pago proveedor", "0.00", "400.00"),
                (3, "2026-03-20", "Cobro cliente", "250.50", "0.00"),
            ]
        def close(self):
            pass

    class FakeConn:
        def cursor(self):
            return FakeCursor()

    monkeypatch.setattr(
        "app.domain.accounting.services.get_legal_readonly_connection",
        lambda client_id: FakeConn()
    )

    ledger = service.get_ledger("tenant_unit", "572000", 2026)
    assert len(ledger) == 3

    assert ledger[0]["debit"] == Decimal("1000.00")
    assert ledger[0]["credit"] == Decimal("0.00")
    assert ledger[0]["progressive_balance"] == Decimal("1000.00")

    assert ledger[1]["debit"] == Decimal("0.00")
    assert ledger[1]["credit"] == Decimal("400.00")
    assert ledger[1]["progressive_balance"] == Decimal("600.00")

    assert ledger[2]["debit"] == Decimal("250.50")
    assert ledger[2]["credit"] == Decimal("0.00")
    assert ledger[2]["progressive_balance"] == Decimal("850.50")
    assert isinstance(ledger[2]["progressive_balance"], Decimal)



