"""Pruebas unitarias para el servicio legal de facturación (T010 - TDD).

Valida la emisión atómica, inmutabilidad y cálculo de importes bajo la nueva interfaz IVeriFactuService.
"""

from datetime import date
from decimal import Decimal
import pytest

from app.domain.accounting.ports import IssueInvoiceCommand
from app.domain.accounting.verifactu_service import VeriFactuService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    conn = get_legal_connection("test_tenant_legal")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS legal_invoices (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            invoice_number TEXT NOT NULL UNIQUE,
            issue_date TEXT NOT NULL,
            recipient_tax_id TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            taxable_base REAL NOT NULL,
            tax_rate REAL NOT NULL,
            tax_amount REAL NOT NULL,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL,
            verifactu_hash TEXT NOT NULL,
            previous_hash TEXT,
            qr_payload TEXT NOT NULL,
            is_rectified INTEGER DEFAULT 0,
            rectified_invoice_number TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("DELETE FROM legal_invoices WHERE tenant_id = 'test_tenant_legal'")
    conn.commit()
    cursor.close()
    return "test_tenant_legal"


def test_issue_legal_invoice_calculates_totals_and_issues(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    
    cmd = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        issue_date=date(2026, 9, 30),
        recipient_tax_id="B99999999",
        recipient_name="Cliente Prueba SL",
        taxable_base=Decimal("1000.00"),
        tax_rate=Decimal("21.00"),
        description="Servicios de consultoría contable",
    )
    
    invoice = service.issue_legal_invoice(cmd)
    
    assert invoice.invoice_number.startswith("F2026-")
    assert invoice.taxable_base == Decimal("1000.00")
    assert invoice.tax_amount == Decimal("210.00")
    assert invoice.total_amount == Decimal("1210.00")
    assert invoice.status == "ISSUED"
    assert len(invoice.verifactu_hash) == 64  # SHA-256 hex string
    assert "https://" in invoice.qr_payload or "qr" in invoice.qr_payload.lower()


def test_consecutive_invoices_increment_sequence(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    
    cmd1 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="B11111111",
        recipient_name="Cliente Uno",
        taxable_base=Decimal("100.00"),
        tax_rate=Decimal("21.00"),
        description="Factura 1",
    )
    cmd2 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="B22222222",
        recipient_name="Cliente Dos",
        taxable_base=Decimal("200.00"),
        tax_rate=Decimal("21.00"),
        description="Factura 2",
    )
    
    inv1 = service.issue_legal_invoice(cmd1)
    inv2 = service.issue_legal_invoice(cmd2)
    
    num1 = int(inv1.invoice_number.split("-")[1])
    num2 = int(inv2.invoice_number.split("-")[1])
    assert num2 == num1 + 1
