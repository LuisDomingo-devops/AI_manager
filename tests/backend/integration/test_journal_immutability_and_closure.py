"""Tests de Integración para Inmutabilidad Contable, Persistencia Decimal y Cierres (T007/T011 - TDD).
Valida SQLite WAL, almacenamiento TEXT exacto y rollback atómico (Spec 026).
"""
from datetime import date
from decimal import Decimal
import pytest

from app.domain.accounting.ports import JournalLineDTO, RecordJournalEntryCommand
from app.domain.accounting.services import AccountingService
from app.domain.exceptions import UnbalancedJournalEntryError
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    tenant_id = "test_tenant_immutability"
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
    cursor.execute("DROP TABLE IF EXISTS legal_journal_lines")
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
    return tenant_id


def test_atomic_persistence_as_text_in_legal_journal_lines(clean_db):
    """Valida que los importes de debit y credit se persisten como cadenas TEXT exactas en SQLite WAL."""
    tenant_id = clean_db
    service = AccountingService()

    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Factura de alta tecnología",
        lines=[
            JournalLineDTO(account_code="430000", concept="Cliente Beta", debit=Decimal("1234.56"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Servicio IA", debit=Decimal("0.00"), credit=Decimal("1234.56")),
        ]
    )

    entry = service.record_entry(cmd)
    assert entry.is_balanced is True

    # Verificar en la base de datos legal el tipo y formato exacto
    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("SELECT account_code, debit, credit FROM legal_journal_lines WHERE entry_id = ?", (entry.id,))
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) == 2
    for row in rows:
        account_code, debit_val, credit_val = row
        assert isinstance(debit_val, str)
        assert isinstance(credit_val, str)
        if account_code == "430000":
            assert debit_val == "1234.56"
            assert credit_val == "0.00"
        else:
            assert debit_val == "0.00"
            assert credit_val == "1234.56"


def test_unbalanced_entry_rolls_back_atomically(clean_db):
    """Valida que un asiento descuadrado es rechazado y no deja rastros en la base de datos."""
    tenant_id = clean_db
    service = AccountingService()

    cmd = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 10, 1),
        fiscal_year=2026,
        concept="Intento de asiento descuadrado",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("500.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ingreso", debit=Decimal("0.00"), credit=Decimal("499.99")),
        ]
    )

    with pytest.raises(UnbalancedJournalEntryError):
        service.record_entry(cmd)

    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM legal_journal_entries WHERE tenant_id = ?", (tenant_id,))
    count_entries = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM legal_journal_lines")
    count_lines = cursor.fetchone()[0]
    cursor.close()

    assert count_entries == 0
    assert count_lines == 0


def test_closed_fiscal_year_blocks_new_entries_and_ensures_immutability(clean_db):
    """Valida que cerrar un ejercicio bloquea nuevos asientos y persiste is_closed=1 en legal_fiscal_years (T011)."""
    from app.domain.exceptions import FiscalYearClosedError

    tenant_id = clean_db
    service = AccountingService()

    # 1. Registrar asiento en ejercicio abierto 2025
    cmd_open = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2025, 6, 15),
        fiscal_year=2025,
        concept="Asiento ordinario 2025",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("100.00")),
        ]
    )
    entry_open = service.record_entry(cmd_open)
    assert entry_open.entry_number == 1

    # 2. Cerrar formalmente el ejercicio 2025
    assert service.is_fiscal_year_closed(tenant_id, 2025) is False
    closed_ok = service.close_fiscal_year(tenant_id, 2025, closed_by="auditor_test")
    assert closed_ok is True
    assert service.is_fiscal_year_closed(tenant_id, 2025) is True

    # 3. Intentar registrar un nuevo asiento con fecha de 2025 debe ser bloqueado con FiscalYearClosedError
    cmd_blocked = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2025, 12, 31),
        fiscal_year=2025,
        concept="Intento de apunte en año cerrado",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("50.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("50.00")),
        ]
    )

    with pytest.raises(FiscalYearClosedError):
        service.record_entry(cmd_blocked)

    # 4. Verificar que el ejercicio 2026 sí sigue abierto y permite asientos
    cmd_2026 = RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 10),
        fiscal_year=2026,
        concept="Asiento en nuevo año abierto 2026",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("200.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("200.00")),
        ]
    )
    entry_2026 = service.record_entry(cmd_2026)
    assert entry_2026.entry_number == 1


def test_post_rectification_entry_integration(clean_db):
    """Valida la inserción real en base de datos legal de facturas rectificativas emitidas y recibidas (T015)."""
    from app.domain.accounting.ports import PostRectificationInvoiceCommand

    tenant_id = clean_db
    service = AccountingService()

    # 1. Factura rectificativa emitida
    cmd_rect_sales = PostRectificationInvoiceCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 7, 10),
        fiscal_year=2026,
        invoice_number="R2026-0001",
        rectified_invoice_number="F2026-0001",
        taxable_base=Decimal("500.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("105.00"),
        total_amount=Decimal("605.00"),
        third_party_account="430000",
        is_sales=True
    )
    entry_sales = service.post_rectification_entry(cmd_rect_sales)
    assert entry_sales.entry_number == 1
    assert entry_sales.is_balanced is True

    # 2. Factura rectificativa recibida
    cmd_rect_purchases = PostRectificationInvoiceCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 7, 12),
        fiscal_year=2026,
        invoice_number="ABONO-PROV-001",
        rectified_invoice_number="FAC-PROV-001",
        taxable_base=Decimal("200.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("42.00"),
        total_amount=Decimal("242.00"),
        third_party_account="400000",
        is_sales=False
    )
    entry_purchases = service.post_rectification_entry(cmd_rect_purchases)
    assert entry_purchases.entry_number == 2
    assert entry_purchases.is_balanced is True


def test_official_books_foliation_and_ledger_integration(clean_db):
    """Valida la generación del Libro Diario oficial correlativo y el Libro Mayor con saldos acumulados (T019)."""
    from app.domain.services.accounting_reporting_service import AccountingReportingService

    tenant_id = clean_db
    service = AccountingService()
    reporting_service = AccountingReportingService()

    # 1. Asiento 1: Aportación inicial / Banco (572 a 100)
    service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 2),
        fiscal_year=2026,
        concept="Constitución de sociedad",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("3000.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="100000", concept="Capital social", debit=Decimal("0.00"), credit=Decimal("3000.00")),
        ]
    ))

    # 2. Asiento 2: Pago alquiler por banco (621 + 472 a 572)
    service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 5),
        fiscal_year=2026,
        concept="Pago arrendamiento enero",
        lines=[
            JournalLineDTO(account_code="621000", concept="Arrendamientos", debit=Decimal("500.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="472000", concept="IVA Soportado", debit=Decimal("105.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("0.00"), credit=Decimal("605.00")),
        ]
    ))

    # 3. Asiento 3: Cobro cliente por banco (572 a 700 + 477)
    service.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 15),
        fiscal_year=2026,
        concept="Venta de servicios y cobro",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("1210.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Prestación de servicios", debit=Decimal("0.00"), credit=Decimal("1000.00")),
            JournalLineDTO(account_code="477000", concept="IVA Repercutido", debit=Decimal("0.00"), credit=Decimal("210.00")),
        ]
    ))

    # Verificar Libro Mayor de Tesorería (572000)
    ledger_572 = service.get_ledger(tenant_id, "572000", 2026)
    assert len(ledger_572) == 3

    assert ledger_572[0]["entry_number"] == 1
    assert ledger_572[0]["debit"] == Decimal("3000.00")
    assert ledger_572[0]["progressive_balance"] == Decimal("3000.00")

    assert ledger_572[1]["entry_number"] == 2
    assert ledger_572[1]["credit"] == Decimal("605.00")
    assert ledger_572[1]["progressive_balance"] == Decimal("2395.00")

    assert ledger_572[2]["entry_number"] == 3
    assert ledger_572[2]["debit"] == Decimal("1210.00")
    assert ledger_572[2]["progressive_balance"] == Decimal("3605.00")

    # Verificar Libro Diario Oficial foliado
    daily_book = reporting_service.generate_official_daily_book(tenant_id, 2026)
    assert daily_book["tenant_id"] == tenant_id
    assert daily_book["fiscal_year"] == 2026
    assert daily_book["is_balanced"] is True
    assert daily_book["is_foliated_correlative"] is True
    assert daily_book["total_entries"] == 3
    assert daily_book["total_debit"] == Decimal("4815.00")
    assert daily_book["total_credit"] == Decimal("4815.00")



