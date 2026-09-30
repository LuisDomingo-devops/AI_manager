"""Pruebas unitarias para el encadenamiento SHA-256 VeriFactu (T011 - TDD).

Valida el cálculo encadenado de huellas criptográficas y la detección de alteraciones históricas.
"""

from decimal import Decimal
import pytest

from app.domain.accounting.ports import IssueInvoiceCommand
from app.domain.accounting.verifactu_service import VeriFactuService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    conn = get_legal_connection("test_tenant_chain")
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
    cursor.execute("DELETE FROM legal_invoices WHERE tenant_id = 'test_tenant_chain'")
    conn.commit()
    cursor.close()
    return "test_tenant_chain"


def test_verifactu_chain_links_hashes(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    
    cmd1 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="A11111111",
        recipient_name="Empresa A",
        taxable_base=Decimal("500.00"),
        tax_rate=Decimal("21.00"),
        description="Servicio 1",
    )
    cmd2 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="A22222222",
        recipient_name="Empresa B",
        taxable_base=Decimal("800.00"),
        tax_rate=Decimal("21.00"),
        description="Servicio 2",
    )
    
    inv1 = service.issue_legal_invoice(cmd1)
    inv2 = service.issue_legal_invoice(cmd2)
    
    # inv2 debe encadenar el hash de inv1
    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("SELECT previous_hash, verifactu_hash FROM legal_invoices WHERE invoice_number = ?", (inv2.invoice_number,))
    row = cursor.fetchone()
    cursor.close()
    
    assert row is not None
    assert row[0] == inv1.verifactu_hash
    assert service.verify_chain_integrity(tenant_id, 2026) is True


def test_tampering_with_chain_breaks_integrity_verification(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    
    cmd1 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="A11111111",
        recipient_name="Empresa A",
        taxable_base=Decimal("100.00"),
        tax_rate=Decimal("21.00"),
        description="Servicio 1",
    )
    cmd2 = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="A22222222",
        recipient_name="Empresa B",
        taxable_base=Decimal("200.00"),
        tax_rate=Decimal("21.00"),
        description="Servicio 2",
    )
    
    inv1 = service.issue_legal_invoice(cmd1)
    service.issue_legal_invoice(cmd2)
    
    # Simular una manipulación ilícita en la base de datos sobre la factura 1
    conn = get_legal_connection(tenant_id)
    cursor = conn.cursor()
    cursor.execute("UPDATE legal_invoices SET taxable_base = 999.00 WHERE invoice_number = ?", (inv1.invoice_number,))
    conn.commit()
    cursor.close()
    
    # La verificación criptográfica debe fallar
    assert service.verify_chain_integrity(tenant_id, 2026) is False
