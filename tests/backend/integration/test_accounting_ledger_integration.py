"""Pruebas de integración para el Libro Diario y Mayor PGC (T012 - TDD).

Valida que los asientos contables generados cuadren (Debe == Haber) y se consulten en el Libro Mayor.
"""

from datetime import date
from decimal import Decimal
import pytest

from app.domain.accounting.ports import RecordJournalEntryCommand
from app.domain.accounting.services import AccountingService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    conn = get_legal_connection("test_tenant_ledger")
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
    cursor.execute("DELETE FROM legal_journal_lines WHERE entry_id IN (SELECT id FROM legal_journal_entries WHERE tenant_id = 'test_tenant_ledger')")
    cursor.execute("DELETE FROM legal_journal_entries WHERE tenant_id = 'test_tenant_ledger'")
    conn.commit()
    cursor.close()
    return "test_tenant_ledger"


def test_record_balanced_journal_entry(clean_db):
    tenant_id = clean_db
    service = AccountingService()
    
    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 9, 30),
        fiscal_year=2026,
        concept="Factura emitida F2026-0001",
        document_ref="F2026-0001",
        lines=[
            {"account": "430000", "debit": 1210.00, "credit": 0.00},   # Clientes
            {"account": "700000", "debit": 0.00, "credit": 1000.00},   # Ventas
            {"account": "477000", "debit": 0.00, "credit": 210.00},    # IVA repercutido
        ]
    )
    
    entry = service.record_entry(cmd)
    
    assert entry.entry_number >= 1
    assert entry.is_balanced is True
    
    # Comprobar consulta de Libro Mayor para cuenta de clientes 430000
    ledger = service.get_ledger(tenant_id, "430000", 2026)
    assert len(ledger) >= 1
    assert ledger[0]["debit"] == 1210.00
    assert ledger[0]["credit"] == 0.00


def test_unbalanced_journal_entry_raises_error(clean_db):
    tenant_id = clean_db
    service = AccountingService()
    
    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 9, 30),
        fiscal_year=2026,
        concept="Asiento descuadrado ilícito",
        lines=[
            {"account": "430000", "debit": 1000.00, "credit": 0.00},
            {"account": "700000", "debit": 0.00, "credit": 800.00},  # Descuadre de 200
        ]
    )
    
    with pytest.raises(ValueError, match="descuadrado"):
        service.record_entry(cmd)
