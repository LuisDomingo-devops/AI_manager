"""
Suite de QA para el Flujo de Conciliación Bancaria y Casación Inteligente (User Story 5).
Valida el algoritmo ponderado de coincidencia y la confirmación humana de conciliación.
"""

import pytest
from app.domain.services.bank_reconciliation_engine import BankReconciliationEngine
from app.domain.models.billing import BankEntryDTO, InvoiceDTO, InvoiceType, InvoiceStatus


def test_qa_reconciliation_intelligent_matching_and_scoring():
    """Valida el cálculo de correspondencias entre apuntes bancarios y facturas abiertas."""
    engine = BankReconciliationEngine()
    
    # Apunte bancario: 1210€ el 16 de enero de 2026 con concepto 'TRANSFERENCIA ACME CORP'
    bank_entry = BankEntryDTO(
        id=101,
        operation_date="2026-01-16",
        value_date="2026-01-16",
        concept="TRANSFERENCIA ACME CORP F2026-0001",
        amount=1210.00,
        balance_after=5210.00,
        reconciliation_status="UNRECONCILED"
    )
    
    # Factura pendiente: 1210€ el 15 de enero de 2026 para el cliente 'ACME CORP'
    open_invoice = InvoiceDTO(
        id=201,
        series="F2026",
        number=1,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-15",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B12345674",
        recipient_name="ACME CORP",
        base_amount=1000.0,
        tax_amount=210.0,
        total_amount=1210.0,
        status=InvoiceStatus.ISSUED
    )
    
    # Factura no coincidente (otro importe y cliente)
    other_invoice = InvoiceDTO(
        id=202,
        series="F2026",
        number=2,
        invoice_type=InvoiceType.F1,
        issue_date="2026-01-10",
        issuer_nif="12345678Z",
        issuer_name="ALFONSO AUTONOMO",
        recipient_nif="B99999999",
        recipient_name="OTRO CLIENTE",
        base_amount=500.0,
        tax_amount=105.0,
        total_amount=605.0,
        status=InvoiceStatus.ISSUED
    )
    
    suggestions = engine.suggest_matches(
        unlinked_entries=[bank_entry],
        open_invoices=[open_invoice, other_invoice]
    )
    
    assert len(suggestions) == 1
    best_match = suggestions[0]
    assert best_match.entry_id == 101
    assert best_match.invoice_id == 201
    assert best_match.score >= 0.70
    assert "exact_amount" in best_match.matching_criteria
    assert "date_proximity" in best_match.matching_criteria
