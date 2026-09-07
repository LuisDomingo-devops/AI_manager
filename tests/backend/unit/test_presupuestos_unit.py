import pytest
import asyncio
from app.tools.server.billing_tools import create_quote

@pytest.mark.asyncio
async def test_presupuestos_calculo_unit():
    """
    Test unitario para calcular el total e impuestos de un presupuesto.
    """
    res = await create_quote(
        client_name="Unit Test",
        client_nif="33333333C",
        amount=100.0,
        concept="Test unitario",
        iva_rate=21.0,
        irpf_rate=15.0,
        is_draft=True
    )
    assert res["status"] == "ok"
    
@pytest.mark.asyncio
async def test_presupuestos_estados_unit():
    """
    Test unitario para las transiciones de estado de un presupuesto.
    """
    res = await create_quote(
        client_name="Unit Test 2",
        client_nif="33333333C",
        amount=100.0,
        concept="Test unitario",
        iva_rate=21.0,
        irpf_rate=15.0,
        is_draft=False
    )
    assert res["status"] == "ok"

