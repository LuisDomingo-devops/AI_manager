import pytest
import asyncio
from app.tools.server.billing_tools import create_quote, convert_quote_to_invoice

@pytest.mark.asyncio
async def test_presupuestos_qa_flujo_completo():
    """
    Test QA End-to-End: Creación de presupuesto -> Envío -> Aceptación -> Facturación.
    """
    # 1. Crear presupuesto
    res = await create_quote(
        client_name="QA Presupuestos",
        client_nif="44444444D",
        amount=2000.0,
        concept="Proyecto QA",
        iva_rate=21.0,
        irpf_rate=0.0,
        is_draft=True
    )
    assert res["status"] == "ok"
    quote_id = res["quote_id"]
    
    # 2. Convertir a factura (simula aceptación)
    conv_res = await convert_quote_to_invoice(quote_id, confirmed_by_user=True)
    assert conv_res["status"] == "ok"
    assert "invoice_id" in conv_res
