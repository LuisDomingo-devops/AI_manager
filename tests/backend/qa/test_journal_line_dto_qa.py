"""Tests de QA para el flujo contable estricto con JournalLineDTO.
Valida la integridad de múltiples transacciones contables del PGC.
"""
from datetime import date
from decimal import Decimal
import pytest

from app.domain.accounting.ports import JournalLineDTO, RecordJournalEntryCommand
from app.domain.accounting.services import AccountingService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    tenant_id = "test_tenant_dto_qa"
    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_journal_entries (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            entry_number INTEGER NOT NULL,
            entry_date TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            concept TEXT NOT NULL,
            document_ref TEXT,
            is_closed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_journal_lines (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,
            account_code TEXT NOT NULL,
            debit REAL DEFAULT 0.0,
            credit REAL DEFAULT 0.0,
            FOREIGN KEY (entry_id) REFERENCES legal_journal_entries(id)
        )
    """)
    cursor.execute("DELETE FROM legal_journal_lines WHERE entry_id IN (SELECT id FROM legal_journal_entries WHERE tenant_id = ?)", (tenant_id,))
    cursor.execute("DELETE FROM legal_journal_entries WHERE tenant_id = ?", (tenant_id,))
    conn.commit()
    cursor.close()
    return tenant_id


def test_qa_accounting_multi_transaction_lifecycle_with_journal_line_dtos(clean_db):
    """QA Suite: Flujo de operaciones secuenciales (Apertura -> Venta -> Cobro) con JournalLineDTO."""
    tenant_id = clean_db
    service = AccountingService()

    # 1. Asiento de Apertura
    entry_apertura = service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 1),
        fiscal_year=2026,
        concept="Asiento de apertura 2026",
        lines=[
            JournalLineDTO(account_code="572000", concept="Saldo inicial banco", debit=Decimal("5000.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="100000", concept="Capital social", debit=Decimal("0.00"), credit=Decimal("5000.00")),
        ]
    ))
    assert entry_apertura.entry_number == 1
    assert entry_apertura.is_balanced is True

    # 2. Asiento de Venta de Servicios (Base 2000 € + 21% IVA = 2420 €)
    entry_venta = service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 2, 15),
        fiscal_year=2026,
        concept="Factura cliente F2026-0001",
        document_ref="F2026-0001",
        lines=[
            JournalLineDTO(account_code="430000", concept="Cliente Alfa", debit=Decimal("2420.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Prestación servicios", debit=Decimal("0.00"), credit=Decimal("2000.00")),
            JournalLineDTO(account_code="477000", concept="IVA devengado 21%", debit=Decimal("0.00"), credit=Decimal("420.00")),
        ]
    ))
    assert entry_venta.entry_number == 2
    assert entry_venta.is_balanced is True

    # 3. Asiento de Cobro del Cliente por Banco
    entry_cobro = service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 2, 20),
        fiscal_year=2026,
        concept="Cobro transferencia F2026-0001",
        document_ref="TRF-001",
        lines=[
            JournalLineDTO(account_code="572000", concept="Entrada en cuenta bancaria", debit=Decimal("2420.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="430000", concept="Cancelación saldo cliente", debit=Decimal("0.00"), credit=Decimal("2420.00")),
        ]
    ))
    assert entry_cobro.entry_number == 3
    assert entry_cobro.is_balanced is True

    # Verificación en Libro Mayor: Cuenta de banco 572000 debe tener 2 movimientos sumando 7420.00
    ledger_banco = service.get_ledger(tenant_id, "572000", 2026)
    assert len(ledger_banco) == 2
    total_banco_debit = sum(Decimal(str(mov["debit"])) for mov in ledger_banco)
    assert total_banco_debit == Decimal("7420.00")

    # Verificación en Libro Mayor: Cuenta de cliente 430000 debe quedar saldada (Debe 2420.00 == Haber 2420.00)
    ledger_cliente = service.get_ledger(tenant_id, "430000", 2026)
    assert len(ledger_cliente) == 2
    total_cli_debit = sum(Decimal(str(mov["debit"])) for mov in ledger_cliente)
    total_cli_credit = sum(Decimal(str(mov["credit"])) for mov in ledger_cliente)
    assert total_cli_debit == total_cli_credit == Decimal("2420.00")
