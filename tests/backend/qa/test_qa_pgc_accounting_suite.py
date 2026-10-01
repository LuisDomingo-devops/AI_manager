"""Suite de Control de Calidad (QA) para el Núcleo Contable PGC con Decimal e Inmutabilidad.

Especificación: 026-contabilidad-pgc-decimal-inmutable
Normativa: Código de Comercio (Arts. 25-33), RD 1514/2007 (PGC), RD 1619/2012 (Reglamento de Facturación).
"""

from datetime import date
from decimal import Decimal
import uuid
import pytest

from app.domain.accounting.ports import (
    JournalLineDTO,
    RecordJournalEntryCommand,
    PostRectificationInvoiceCommand,
)
from app.domain.accounting.services import AccountingService
from app.domain.services.accounting_reporting_service import AccountingReportingService
from app.domain.exceptions import UnbalancedJournalEntryError, FiscalYearClosedError
from app.infrastructure.database.legal_connection import (
    legal_write_transaction,
    get_legal_readonly_connection,
)


@pytest.fixture
def qa_tenant(clean_db_conn):
    """Proporciona un tenant limpio con esquema legal preparado para la suite de QA."""
    tenant = f"test_qa_{uuid.uuid4().hex[:8]}"
    with legal_write_transaction(client_id=tenant) as conn:
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS legal_journal_lines")
        cursor.execute("DROP TABLE IF EXISTS legal_journal_entries")
        cursor.execute("DROP TABLE IF EXISTS legal_fiscal_years")
        cursor.execute("""
            CREATE TABLE legal_fiscal_years (
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
            CREATE TABLE legal_journal_entries (
                id TEXT PRIMARY KEY,
                entry_number INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                fiscal_year INTEGER NOT NULL,
                concept TEXT NOT NULL,
                document_ref TEXT,
                is_balanced INTEGER NOT NULL DEFAULT 1,
                is_closed INTEGER NOT NULL DEFAULT 0,
                tenant_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (tenant_id, fiscal_year, entry_number)
            )
        """)
        cursor.execute("""
            CREATE TABLE legal_journal_lines (
                id TEXT PRIMARY KEY,
                entry_id TEXT NOT NULL,
                account_code TEXT NOT NULL,
                concept TEXT,
                debit TEXT NOT NULL,
                credit TEXT NOT NULL,
                FOREIGN KEY (entry_id) REFERENCES legal_journal_entries(id)
            )
        """)
        cursor.close()
    return tenant


def test_qa_decimal_exactness_and_text_storage(qa_tenant):
    """QA 1: Verifica que las cantidades se guarden en columnas TEXT y mantengan precisión Decimal exacta."""
    service = AccountingService()

    exact_amount = Decimal("1234567.89")
    cmd = RecordJournalEntryCommand(
        tenant_id=qa_tenant,
        entry_date=date(2026, 4, 1),
        fiscal_year=2026,
        concept="Apunte de prueba alta precisión",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=exact_amount, credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=exact_amount),
        ]
    )
    entry = service.record_entry(cmd)
    assert entry.is_balanced is True

    # Verificar directamente en SQLite que se almacenó como TEXT
    conn = get_legal_readonly_connection(client_id=qa_tenant)
    cursor = conn.cursor()
    cursor.execute("SELECT debit, credit, typeof(debit), typeof(credit) FROM legal_journal_lines WHERE entry_id = ?", (entry.id,))
    rows = cursor.fetchall()
    cursor.close()

    assert len(rows) == 2
    assert rows[0][0] == "1234567.89"
    assert rows[0][2] == "text"
    assert rows[1][1] == "1234567.89"
    assert rows[1][3] == "text"


def test_qa_zero_tolerance_unbalance_rejection(qa_tenant):
    """QA 2: Verifica que cualquier desbalance, incluso de 0.01 €, sea rechazado inmediatamente."""
    service = AccountingService()

    cmd_unbalanced = RecordJournalEntryCommand(
        tenant_id=qa_tenant,
        entry_date=date(2026, 4, 2),
        fiscal_year=2026,
        concept="Asiento descuadrado",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("100.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("99.99")),
        ]
    )

    with pytest.raises(UnbalancedJournalEntryError) as exc_info:
        service.record_entry(cmd_unbalanced)

    assert exc_info.value.total_debit == Decimal("100.00")
    assert exc_info.value.total_credit == Decimal("99.99")


def test_qa_closed_fiscal_year_immutability_lockdown(qa_tenant):
    """QA 3: Verifica el bloqueo estricto de cualquier apunte posterior al cierre formal del ejercicio."""
    service = AccountingService()

    # Asentar en 2025
    service.record_entry(RecordJournalEntryCommand(
        tenant_id=qa_tenant,
        entry_date=date(2025, 12, 1),
        fiscal_year=2025,
        concept="Operación antes del cierre",
        lines=[
            JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("500.00"), credit=Decimal("0.00")),
            JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("500.00")),
        ]
    ))

    # Cierre de ejercicio
    assert service.close_fiscal_year(qa_tenant, 2025, closed_by="auditor_qa") is True
    assert service.is_fiscal_year_closed(qa_tenant, 2025) is True

    # Intento de inserción en ejercicio cerrado
    with pytest.raises(FiscalYearClosedError) as exc_info:
        service.record_entry(RecordJournalEntryCommand(
            tenant_id=qa_tenant,
            entry_date=date(2025, 12, 31),
            fiscal_year=2025,
            concept="Fraude o alteración extemporánea",
            lines=[
                JournalLineDTO(account_code="572000", concept="Banco", debit=Decimal("10.00"), credit=Decimal("0.00")),
                JournalLineDTO(account_code="700000", concept="Ventas", debit=Decimal("0.00"), credit=Decimal("10.00")),
            ]
        ))
    assert exc_info.value.fiscal_year == 2025


def test_qa_rectification_invoices_pgc_reversal(qa_tenant):
    """QA 4: Verifica el registro de facturas rectificativas minorando ingresos (708) y compras (608)."""
    service = AccountingService()

    # Factura rectificativa emitida
    sales_rect = service.post_rectification_entry(PostRectificationInvoiceCommand(
        tenant_id=qa_tenant,
        entry_date=date(2026, 5, 10),
        fiscal_year=2026,
        invoice_number="R2026-0099",
        rectified_invoice_number="F2026-0010",
        taxable_base=Decimal("1000.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("210.00"),
        total_amount=Decimal("1210.00"),
        third_party_account="430000",
        is_sales=True
    ))
    assert sales_rect.is_balanced is True

    # Comprobar líneas de la rectificativa emitida
    ledger_708 = service.get_ledger(qa_tenant, "708000", 2026)
    assert len(ledger_708) == 1
    assert ledger_708[0]["debit"] == Decimal("1000.00")

    ledger_477 = service.get_ledger(qa_tenant, "477000", 2026)
    assert len(ledger_477) == 1
    assert ledger_477[0]["debit"] == Decimal("210.00")

    # Factura rectificativa recibida
    purchase_rect = service.post_rectification_entry(PostRectificationInvoiceCommand(
        tenant_id=qa_tenant,
        entry_date=date(2026, 5, 12),
        fiscal_year=2026,
        invoice_number="ABONO-PROV-88",
        rectified_invoice_number="FAC-PROV-12",
        taxable_base=Decimal("400.00"),
        tax_rate=Decimal("21.00"),
        tax_amount=Decimal("84.00"),
        total_amount=Decimal("484.00"),
        third_party_account="400000",
        is_sales=False
    ))
    assert purchase_rect.is_balanced is True

    ledger_608 = service.get_ledger(qa_tenant, "608000", 2026)
    assert len(ledger_608) == 1
    assert ledger_608[0]["credit"] == Decimal("400.00")


def test_qa_official_daily_and_ledger_books_compliance(qa_tenant):
    """QA 5: Verifica la foliación ininterrumpida del Libro Diario y los saldos progresivos del Libro Mayor."""
    service = AccountingService()
    reporting_service = AccountingReportingService()

    # Crear 5 asientos correlativos
    for i in range(1, 6):
        service.record_entry(RecordJournalEntryCommand(
            tenant_id=qa_tenant,
            entry_date=date(2026, 6, i),
            fiscal_year=2026,
            concept=f"Operación día {i}",
            lines=[
                JournalLineDTO(account_code="572000", concept="Tesorería", debit=Decimal("100.00"), credit=Decimal("0.00")),
                JournalLineDTO(account_code="700000", concept="Ingresos", debit=Decimal("0.00"), credit=Decimal("100.00")),
            ]
        ))

    # Libro Diario Oficial
    daily_book = reporting_service.generate_official_daily_book(qa_tenant, 2026)
    assert daily_book["is_foliated_correlative"] is True
    assert daily_book["is_balanced"] is True
    assert daily_book["total_entries"] == 5
    assert daily_book["total_debit"] == Decimal("500.00")
    assert daily_book["total_credit"] == Decimal("500.00")

    # Libro Mayor progresivo
    ledger_572 = service.get_ledger(qa_tenant, "572000", 2026)
    assert len(ledger_572) == 5
    for idx, mov in enumerate(ledger_572, start=1):
        assert mov["entry_number"] == idx
        assert mov["progressive_balance"] == Decimal(f"{idx * 100}.00")
