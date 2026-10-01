"""Tests de Integración para JournalLineDTO con AccountingService.
Valida la interoperabilidad y persistencia de asientos con DTOs fuertemente tipados.
"""
from datetime import date
from decimal import Decimal
import pytest

from app.domain.accounting.ports import JournalLineDTO, RecordJournalEntryCommand
from app.domain.accounting.services import AccountingService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    tenant_id = "test_tenant_dto_integration"
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


def test_accounting_service_records_entry_with_journal_line_dtos(clean_db):
    """Valida que AccountingService acepta RecordJournalEntryCommand con JournalLineDTOs."""
    tenant_id = clean_db
    service = AccountingService()

    lines = [
        JournalLineDTO(account_code="430000", concept="Cliente ACME", debit=Decimal("1210.00"), credit=Decimal("0.00")),
        JournalLineDTO(account_code="700000", concept="Venta servicios", debit=Decimal("0.00"), credit=Decimal("1000.00")),
        JournalLineDTO(account_code="477000", concept="IVA repercutido 21%", debit=Decimal("0.00"), credit=Decimal("210.00")),
    ]

    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Factura emitida ACME-001",
        document_ref="ACME-001",
        lines=lines
    )

    entry = service.record_entry(cmd)

    assert entry.entry_number >= 1
    assert entry.is_balanced is True

    # Comprobar consulta en el Libro Mayor
    ledger_430 = service.get_ledger(tenant_id, "430000", 2026)
    assert len(ledger_430) == 1
    assert ledger_430[0]["debit"] == 1210.00
    assert ledger_430[0]["credit"] == 0.00


def test_accounting_service_records_entry_with_dict_lines_automatically_converted(clean_db):
    """Valida la compatibilidad hacia atrás cuando se envían diccionarios a RecordJournalEntryCommand."""
    tenant_id = clean_db
    service = AccountingService()

    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Factura recibida PROV-001",
        document_ref="PROV-001",
        lines=[
            {"account": "600000", "debit": 500.00, "credit": 0.00},
            {"account": "472000", "debit": 105.00, "credit": 0.00},
            {"account": "400000", "debit": 0.00, "credit": 605.00},
        ]
    )

    entry = service.record_entry(cmd)

    assert entry.entry_number >= 1
    assert entry.is_balanced is True
    assert all(isinstance(line, JournalLineDTO) for line in cmd.lines)
