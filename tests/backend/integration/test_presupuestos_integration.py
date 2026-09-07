import pytest
import asyncio
from app.tools.server.billing_tools import create_quote, get_quotes, convert_quote_to_invoice
from app.adapters.memory.memory import _get_connection
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository

@pytest.mark.asyncio
async def test_presupuestos_db_integration():
    """
    Test de integración: almacenamiento de presupuesto.
    """
    res = await create_quote(
        client_name="Cliente Presupuesto Int",
        client_nif="11111111A",
        amount=500.0,
        concept="Desarrollo Test",
        iva_rate=21.0,
        irpf_rate=0.0,
        is_draft=True
    )
    assert res["status"] == "ok"
    quote_id = res["quote_id"]
    
    # Comprobar si se almacenó
    quotes = await get_quotes()
    found = next((q for q in quotes["quotes"] if q["quote_id"] == quote_id), None)
    assert found is not None
    assert found["client_name"] == "Cliente Presupuesto Int"

@pytest.mark.asyncio
async def test_presupuestos_a_factura_integration():
    """
    Test de integración: conversión de presupuesto a factura.
    """
    res = await create_quote(
        client_name="Cliente A Facturar",
        client_nif="22222222B",
        amount=1000.0,
        concept="Conversión Test",
        iva_rate=21.0,
        irpf_rate=15.0,
        is_draft=True
    )
    assert res["status"] == "ok"
    quote_id = res["quote_id"]
    
    # Convertir
    conv_res = await convert_quote_to_invoice(quote_id, confirmed_by_user=True)
    assert conv_res["status"] == "ok"
    
    invoice_id = conv_res["invoice_id"]
    # Comprobar que la factura existe
    inv = InvoiceRepository.find_invoice_by_id(invoice_id)
    assert inv is not None
    assert inv["base_imponible"] == 1000.0
    
    # Comprobar que el estado del presupuesto cambió a facturado
    quotes = await get_quotes()
    found = next((q for q in quotes["quotes"] if q["quote_id"] == quote_id), None)
    assert found is not None
    assert found["status"] == "facturado"
