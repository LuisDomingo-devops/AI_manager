"""Prueba de QA de estrés: Resiliencia del Núcleo Contable durante Caída de IA (T022 - TDD).

Valida que si la pasarela de IA colapsa completamente con errores de red o cuota,
la emisión de facturas oficiales y el Libro Diario continúan operando con 0 fallos.
"""

from decimal import Decimal
from unittest.mock import AsyncMock, patch
import pytest
import httpx

from app.domain.accounting.ports import IssueInvoiceCommand
from app.domain.accounting.verifactu_service import VeriFactuService
from app.infrastructure.ai_gateway.client import CloudflareAIGatewayClient
from app.infrastructure.database.legal_connection import get_legal_connection


@pytest.fixture
def clean_db():
    conn = get_legal_connection("test_tenant_qa_stress_ai")
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
    cursor.execute("DELETE FROM legal_invoices WHERE tenant_id = 'test_tenant_qa_stress_ai'")
    conn.commit()
    cursor.close()
    return "test_tenant_qa_stress_ai"


@pytest.mark.asyncio
async def test_legal_billing_succeeds_even_when_ai_gateway_fails_completely(clean_db):
    tenant_id = clean_db
    
    # 1. Simular colapso completo en la pasarela de IA mediante excepción de Timeout
    ai_client = CloudflareAIGatewayClient(
        worker_url="https://alfonso-worker.test.workers.dev",
        license_token="token"
    )
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectTimeout("Connection to Cloudflare Worker timed out")
        
        # La llamada de IA falla de forma controlada sin propagar excepción al hilo
        ai_response = await ai_client.generate_content("Explicación de impuestos para factura")
        assert ai_response.success is False
        assert ai_response.error_code in ("TIMEOUT", "NETWORK_ERROR")
    
    # 2. La emisión de facturas oficiales opera al 100% de forma autónoma
    billing_service = VeriFactuService()
    cmd = IssueInvoiceCommand(
        tenant_id=tenant_id,
        series="F2026",
        recipient_tax_id="B99887766",
        recipient_name="Cliente Durante Caída de IA",
        taxable_base=Decimal("1500.00"),
        tax_rate=Decimal("21.00"),
        description="Factura emitida en modo contingencia de IA",
    )
    
    invoice = billing_service.issue_legal_invoice(cmd)
    
    assert invoice.status == "ISSUED"
    assert invoice.total_amount == Decimal("1815.00")
    assert len(invoice.verifactu_hash) == 64
    assert billing_service.verify_chain_integrity(tenant_id, 2026) is True
