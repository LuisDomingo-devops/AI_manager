import pytest
from decimal import Decimal
from datetime import date
from app.infrastructure.database.tenant_context import (
    TenantManager,
    tenant_scope,
    get_current_tenant,
    set_current_tenant,
)
from app.domain.accounting.verifactu_service import VeriFactuService
from app.domain.accounting.ports import IssueInvoiceCommand

def test_tenant_context_switching():
    assert get_current_tenant() == "default"
    
    set_current_tenant("empresa_alpha")
    assert get_current_tenant() == "empresa_alpha"
    
    with tenant_scope("empresa_beta"):
        assert get_current_tenant() == "empresa_beta"
        
    assert get_current_tenant() == "empresa_alpha"
    
    set_current_tenant("default")
    assert get_current_tenant() == "default"

def test_multi_company_data_isolation():
    """
    Verifica que las facturas de Empresa Alpha estén estrictamente
    aisladas de Empresa Beta.
    """
    service = VeriFactuService()
    
    # 1. Operar en contexto de Empresa Alpha
    with tenant_scope("empresa_alpha"):
        cmd_alpha = IssueInvoiceCommand(
            tenant_id="empresa_alpha",
            series="ALPHA2026",
            issue_date="2026-09-30",
            recipient_tax_id="B11111111",
            recipient_name="Cliente Alpha",
            description="Servicios profesionales Alpha",
            taxable_base=Decimal("1000.00"),
            tax_rate=Decimal("21.0"),
        )
        invoice_alpha = service.issue_legal_invoice(cmd_alpha)
        assert invoice_alpha.invoice_number == "ALPHA2026-0001"
        assert invoice_alpha.tenant_id == "empresa_alpha"
        
        # Verificar que Alpha tiene su factura
        inv_alpha = service.get_invoice_by_number("empresa_alpha", "ALPHA2026-0001")
        assert inv_alpha is not None
        assert inv_alpha.invoice_number == "ALPHA2026-0001"
        
    # 2. Conmutar a contexto de Empresa Beta
    with tenant_scope("empresa_beta"):
        # Empresa Beta no debe ver facturas de Empresa Alpha
        inv_alpha_in_beta = service.get_invoice_by_number("empresa_beta", "ALPHA2026-0001")
        assert inv_alpha_in_beta is None
        
        # Emitir factura propia de Beta
        cmd_beta = IssueInvoiceCommand(
            tenant_id="empresa_beta",
            series="BETA2026",
            issue_date="2026-09-30",
            recipient_tax_id="B22222222",
            recipient_name="Cliente Beta",
            description="Servicios profesionales Beta",
            taxable_base=Decimal("500.00"),
            tax_rate=Decimal("21.0"),
        )
        invoice_beta = service.issue_legal_invoice(cmd_beta)
        assert invoice_beta.invoice_number == "BETA2026-0001"
        
        inv_beta = service.get_invoice_by_number("empresa_beta", "BETA2026-0001")
        assert inv_beta is not None
        assert inv_beta.invoice_number == "BETA2026-0001"

    # 3. Volver a Empresa Alpha y verificar integridad
    with tenant_scope("empresa_alpha"):
        inv_alpha_check = service.get_invoice_by_number("empresa_alpha", "ALPHA2026-0001")
        assert inv_alpha_check is not None
        assert inv_alpha_check.invoice_number == "ALPHA2026-0001"
        
        # Y Alpha no debe tener la factura de Beta
        inv_beta_in_alpha = service.get_invoice_by_number("empresa_alpha", "BETA2026-0001")
        assert inv_beta_in_alpha is None
