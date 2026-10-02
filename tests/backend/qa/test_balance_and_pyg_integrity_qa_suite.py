"""
Suite de QA para Integridad Contable: Balance de Situación y Cuenta de Pérdidas y Ganancias (User Story 4).
Valida que ninguna cuenta con movimientos quede excluida y que se cumpla la ecuación fundamental contable.
"""

from decimal import Decimal
from datetime import date
import pytest
from app.domain.accounting.services import AccountingService
from app.domain.accounting.ports import RecordJournalEntryCommand
from app.domain.services.accounting_reporting_service import AccountingReportingService


from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_balance_qa_db():
    tenant_id = "test_qa_balance_pyg"
    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_fiscal_years (
            tenant_id TEXT NOT NULL,
            fiscal_year INTEGER NOT NULL,
            is_closed INTEGER NOT NULL DEFAULT 0,
            closed_at TEXT,
            closed_by TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (tenant_id, fiscal_year)
        )
    """)
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (tenant_id, fiscal_year, entry_number)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_journal_lines (
            id TEXT PRIMARY KEY,
            entry_id TEXT NOT NULL,
            account_code TEXT NOT NULL,
            concept TEXT,
            debit TEXT DEFAULT '0.00',
            credit TEXT DEFAULT '0.00',
            FOREIGN KEY (entry_id) REFERENCES legal_journal_entries(id)
        )
    """)
    cursor.execute("DELETE FROM legal_journal_lines WHERE entry_id IN (SELECT id FROM legal_journal_entries WHERE tenant_id = ?)", (tenant_id,))
    cursor.execute("DELETE FROM legal_journal_entries WHERE tenant_id = ?", (tenant_id,))
    cursor.execute("DELETE FROM legal_fiscal_years WHERE tenant_id = ?", (tenant_id,))
    conn.commit()
    cursor.close()
    yield tenant_id


def test_qa_balance_sheet_and_pyg_integrity(clean_balance_qa_db):
    """Valida la generación íntegra y cuadre de Balance de Situación y PyG."""
    accounting = AccountingService()
    reporting = AccountingReportingService()
    tenant_id = clean_balance_qa_db
    fiscal_year = 2026
    
    # 1. Asiento de Inicio / Capital: Banco a Capital
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 1),
        fiscal_year=fiscal_year,
        concept="Constitución / Aportación inicial",
        lines=[
            {"account_code": "57200000", "debit": 10000.0, "credit": 0.0},
            {"account_code": "10000000", "debit": 0.0, "credit": 10000.0}
        ]
    ))
    
    # 2. Venta de Servicios: Clientes a Ventas e IVA
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 2, 1),
        fiscal_year=fiscal_year,
        concept="Factura emitida F2026-0001",
        lines=[
            {"account_code": "43000000", "debit": 2420.0, "credit": 0.0},
            {"account_code": "70500000", "debit": 0.0, "credit": 2000.0},
            {"account_code": "47700021", "debit": 0.0, "credit": 420.0}
        ]
    ))
    
    # 3. Gasto Operativo y Amortización:
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 3, 1),
        fiscal_year=fiscal_year,
        concept="Gastos diversos",
        lines=[
            {"account_code": "62900000", "debit": 500.0, "credit": 0.0},
            {"account_code": "57200000", "debit": 0.0, "credit": 500.0}
        ]
    ))
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 12, 31),
        fiscal_year=fiscal_year,
        concept="Dotación amortización inmovilizado",
        lines=[
            {"account_code": "68100000", "debit": 300.0, "credit": 0.0},
            {"account_code": "28100000", "debit": 0.0, "credit": 300.0}
        ]
    ))
    
    # Generar PyG
    pyg = reporting.generate_profit_and_loss(tenant_id=tenant_id, fiscal_year=fiscal_year)
    assert pyg["total_ingresos"] == 2000.0
    assert pyg["total_gastos"] == 800.0  # 500 (629) + 300 (681)
    assert pyg["resultado_ejercicio"] == 1200.0  # 2000 - 800
    
    # Generar Balance de Situación
    balance = reporting.generate_balance_sheet(tenant_id=tenant_id, fiscal_year=fiscal_year)
    total_activo = balance["total_activo"]
    total_pasivo_pn = balance["total_pasivo_y_patrimonio_neto"]
    
    # Ecuación fundamental: Activo = Pasivo + Patrimonio Neto (incluyendo resultado del ejercicio)
    assert abs(total_activo - total_pasivo_pn) < 0.01, f"Descuadre en Balance: Activo={total_activo}, Pasivo+PN={total_pasivo_pn}"
