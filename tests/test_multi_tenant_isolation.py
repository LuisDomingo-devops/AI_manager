import os
import pytest
from app.adapters.memory.memory import tenant_context, _get_connection
from app.domain.services.tax_parser_service import TaxParserService
from app.tools.server.treasury_tools import get_cash_flow_forecast

@pytest.mark.asyncio
async def test_tenant_database_isolation():
    # 1. Limpiar base de datos para los tenants A y B
    token_a = tenant_context.set("tenant_a")
    conn_a = _get_connection()
    try:
        cursor = conn_a.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        conn_a.commit()
    finally:
        conn_a.close()
        tenant_context.reset(token_a)

    token_b = tenant_context.set("tenant_b")
    conn_b = _get_connection()
    try:
        cursor = conn_b.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        conn_b.commit()
    finally:
        conn_b.close()
        tenant_context.reset(token_b)

    # 2. Registrar datos específicos en tenant_a
    token_a = tenant_context.set("tenant_a")
    try:
        invoice_a = {
            "invoice_id": "INV-TENANT-A-999",
            "date": "2026-08-01",
            "issuer_name": "Luis Domingo Pérez",
            "issuer_nif": "12345678Z",
            "receiver_name": "Cliente de Tenant A",
            "receiver_nif": "B11111111",
            "base_imponible": 1000.0,
            "iva_rate": 21.0,
            "iva_amount": 210.0,
            "irpf_rate": 0.0,
            "irpf_amount": 0.0,
            "total_amount": 1210.0,
            "category": "income",
            "quarter": 3,
            "year": 2026
        }
        TaxParserService.save_invoice_to_db(invoice_a)
        
        # Validar que tenant_a ve su propia factura
        invoices_a = TaxParserService.get_quarterly_aggregates(2026)
        assert len(invoices_a) > 0
        assert any(q["quarter"] == 3 and q["income"]["base"] == 1000.0 for q in invoices_a)
    finally:
        tenant_context.reset(token_a)

    # 3. Validar aislamiento: tenant_b no debe ver la factura de tenant_a
    token_b = tenant_context.set("tenant_b")
    try:
        invoices_b = TaxParserService.get_quarterly_aggregates(2026)
        assert len(invoices_b) == 0
    finally:
        tenant_context.reset(token_b)

    # 4. Registrar datos en tenant_b y validar que no colisionan
    token_b = tenant_context.set("tenant_b")
    try:
        invoice_b = {
            "invoice_id": "INV-TENANT-B-888",
            "date": "2026-08-01",
            "issuer_name": "Empresa B",
            "issuer_nif": "87654321A",
            "receiver_name": "Cliente de Tenant B",
            "receiver_nif": "B22222222",
            "base_imponible": 2000.0,
            "iva_rate": 21.0,
            "iva_amount": 420.0,
            "irpf_rate": 0.0,
            "irpf_amount": 0.0,
            "total_amount": 2420.0,
            "category": "income",
            "quarter": 3,
            "year": 2026
        }
        TaxParserService.save_invoice_to_db(invoice_b)
        
        invoices_b_new = TaxParserService.get_quarterly_aggregates(2026)
        assert len(invoices_b_new) > 0
        assert any(q["quarter"] == 3 and q["income"]["base"] == 2000.0 for q in invoices_b_new)
    finally:
        tenant_context.reset(token_b)

    # 5. Volver a tenant_a y validar que sus datos siguen intactos e inalterados
    token_a = tenant_context.set("tenant_a")
    try:
        invoices_a_final = TaxParserService.get_quarterly_aggregates(2026)
        assert len(invoices_a_final) > 0
        assert any(q["quarter"] == 3 and q["income"]["base"] == 1000.0 for q in invoices_a_final)
    finally:
        tenant_context.reset(token_a)

    # 6. Limpieza de archivos de prueba físicos creados
    for cid in ("tenant_a", "tenant_b"):
        conn = _get_connection(client_id=cid)
        conn.close()
        # Encontrar y borrar archivos test_memory_tenant_a.db y test_memory_tenant_b.db
        from app.adapters.memory.memory import DB_PATH
        db_file = DB_PATH.parent / f"test_memory_{cid}.db"
        if db_file.exists():
            try:
                os.remove(db_file)
            except OSError:
                pass
