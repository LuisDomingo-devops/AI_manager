"""
Tests unitarios para el motor de casación probabilística ponderada de conciliación bancaria.
Valida el cómputo de puntuación (exact_amount +0.50, date_proximity +0.30/+0.15, text_match +0.20)
y la detección y asignación de comisiones bancarias deducidas (cuenta 669).
"""
import pytest
from decimal import Decimal
from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
from app.domain.schemas import BankMovementDTO, ReconciliationSuggestionDTO
from app.domain.models.billing import InvoiceDTO, InvoiceType, InvoiceStatus


def test_matcher_exact_amount_and_date_proximity_three_days():
    """Valida coincidencia con fecha dentro de 3 días (+0.30) e importe exacto (+0.50) y texto (+0.20)."""
    engine = BankReconciliationEngine()

    # Apunte bancario de abono (cobro de cliente) el 18 de enero
    entry = BankMovementDTO(
        id=1,
        account_iban="ES9101821234123456789012",
        operation_date="2026-01-18",
        value_date="2026-01-18",
        amount=Decimal("1210.00"),
        balance_after=Decimal("6210.00"),
        concept="TRANSFERENCIA ACME CORP ESPAÑA F2026-0001",
        reconciliation_status="UNRECONCILED"
    )

    # Factura emitida el 16 de enero (diferencia 2 días <= 3 días -> +0.30)
    invoice = InvoiceDTO(
        id=101,
        series="F2026",
        number=1,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-16",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B12345674",
        recipient_name="ACME CORP ESPAÑA",
        base_amount=1000.0,
        tax_amount=210.0,
        total_amount=1210.0,
        status=InvoiceStatus.ISSUED
    )

    suggestions = engine.suggest_matches(
        unlinked_entries=[entry],
        open_invoices=[invoice],
        min_score=0.70
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.entry_id == 1
    assert s.invoice_id == 101
    assert s.score == 1.00  # 0.50 + 0.30 + 0.20
    assert "exact_amount" in s.matching_criteria
    assert "date_proximity" in s.matching_criteria
    assert "concept_or_counterpart_match" in s.matching_criteria
    assert s.suggested_entry_debit_account == "572"
    assert s.suggested_entry_credit_account == "430"
    assert s.fee_amount == Decimal("0.00")


def test_matcher_date_proximity_week_tier():
    """Valida el tramo de proximidad temporal de 4 a 7 días (+0.15) (U1)."""
    engine = BankReconciliationEngine()

    # Apunte bancario el 22 de enero
    entry = BankMovementDTO(
        id=2,
        account_iban="ES9101821234123456789012",
        operation_date="2026-01-22",
        value_date="2026-01-22",
        amount=Decimal("605.00"),
        balance_after=Decimal("4605.00"),
        concept="PAGO SERVICIOS PROYECTO CLIENTE BETA",
        reconciliation_status="UNRECONCILED"
    )

    # Factura emitida el 16 de enero (diferencia 6 días: 4 <= diff <= 7 -> +0.15)
    invoice = InvoiceDTO(
        id=102,
        series="F2026",
        number=2,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-16",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B99988877",
        recipient_name="CLIENTE BETA SL",
        base_amount=500.0,
        tax_amount=105.0,
        total_amount=605.0,
        status=InvoiceStatus.ISSUED
    )

    suggestions = engine.suggest_matches(
        unlinked_entries=[entry],
        open_invoices=[invoice],
        min_score=0.70
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    # 0.50 (exact_amount) + 0.15 (date_proximity_week) + 0.20 (concept match) = 0.85
    assert s.score == 0.85
    assert "date_proximity_week" in s.matching_criteria


def test_matcher_discards_below_min_score_threshold():
    """Verifica que propuestas con certidumbre < 0.70 son descartadas."""
    engine = BankReconciliationEngine()

    # Apunte bancario con fecha 20 días después y sin texto identificador (solo importe exacto +0.50)
    entry = BankMovementDTO(
        id=3,
        account_iban="ES9101821234123456789012",
        operation_date="2026-02-15",
        value_date="2026-02-15",
        amount=Decimal("300.00"),
        balance_after=Decimal("5300.00"),
        concept="TRANSFERENCIA BANCARIA GENERICA",
        reconciliation_status="UNRECONCILED"
    )

    invoice = InvoiceDTO(
        id=103,
        series="F2026",
        number=3,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-10",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B11223344",
        recipient_name="DISTRIBUCIONES NORTE",
        base_amount=300.0,
        tax_amount=0.0,
        total_amount=300.0,
        status=InvoiceStatus.ISSUED
    )

    suggestions = engine.suggest_matches(
        unlinked_entries=[entry],
        open_invoices=[invoice],
        min_score=0.70
    )

    assert len(suggestions) == 0


def test_matcher_detects_gateway_fees():
    """
    Valida la detección de comisiones bancarias deducidas en cobros (Stripe/TPV) (T015).
    Factura de 1.000,00 € -> Apunte recibido de 975,00 € con concepto 'STRIPE F2026-0004' -> Comisión 25,00 €.
    """
    engine = BankReconciliationEngine()

    entry = BankMovementDTO(
        id=4,
        account_iban="ES9101821234123456789012",
        operation_date="2026-01-20",
        value_date="2026-01-20",
        amount=Decimal("975.00"),
        balance_after=Decimal("5975.00"),
        concept="LIQUIDACION TPV STRIPE F2026-0004",
        reconciliation_status="UNRECONCILED"
    )

    invoice = InvoiceDTO(
        id=104,
        series="F2026",
        number=4,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-19",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B55667788",
        recipient_name="CLIENTE ONLINE SL",
        base_amount=1000.0,
        tax_amount=0.0,
        total_amount=1000.0,
        status=InvoiceStatus.ISSUED
    )

    suggestions = engine.suggest_matches(
        unlinked_entries=[entry],
        open_invoices=[invoice],
        min_score=0.70
    )

    assert len(suggestions) == 1
    s = suggestions[0]
    assert s.entry_id == 4
    assert s.invoice_id == 104
    assert s.fee_amount == Decimal("25.00")
    assert s.score >= 0.70
    assert "amount_with_fee_match" in s.matching_criteria or "exact_amount" in s.matching_criteria
    assert s.suggested_entry_debit_account == "572"
    assert s.suggested_entry_credit_account == "430"
