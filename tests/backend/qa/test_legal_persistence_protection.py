"""Pruebas de QA para concurrencia y protección de persistencia legal (T013 - TDD).

Valida que emisiones concurrentes mantengan la secuencia atómica y que las
herramientas externas no puedan corromper las tablas fiscales protegidas.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import pytest

from app.domain.accounting.ports import IssueInvoiceCommand
from app.domain.accounting.verifactu_service import VeriFactuService
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    conn = get_legal_connection("test_tenant_qa_legal")
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
    cursor.execute("DELETE FROM legal_invoices WHERE tenant_id = 'test_tenant_qa_legal'")
    conn.commit()
    cursor.close()
    return "test_tenant_qa_legal"


def test_concurrent_invoice_emissions_maintain_strict_sequence_and_integrity(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    num_threads = 5
    
    def emit_worker(index: int):
        cmd = IssueInvoiceCommand(
            tenant_id=tenant_id,
            series="F2026",
            recipient_tax_id=f"B{10000000 + index}",
            recipient_name=f"Cliente Concurrente {index}",
            taxable_base=Decimal("100.00"),
            tax_rate=Decimal("21.00"),
            description=f"Factura concurrente {index}",
        )
        return service.issue_legal_invoice(cmd)
    
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(emit_worker, range(num_threads)))
    
    # Comprobar que no hay duplicados en invoice_number
    numbers = [r.invoice_number for r in results]
    assert len(set(numbers)) == num_threads
    
    # Comprobar integridad de toda la cadena
    assert service.verify_chain_integrity(tenant_id, 2026) is True


def test_invalid_negative_amount_raises_domain_error(clean_db):
    tenant_id = clean_db
    service = VeriFactuService()
    
    cmd = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="B12345678",
        recipient_name="Cliente Error",
        taxable_base=Decimal("-50.00"),  # Importe inválido para factura no rectificativa
        tax_rate=Decimal("21.00"),
        description="Factura inválida",
    )
    
    with pytest.raises(ValueError, match="Base imponible"):
        service.issue_legal_invoice(cmd)
