import pytest
import os
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_quotes_lifecycle():
    from app.tools.server.billing_tools import update_quote_status, convert_quote_to_invoice, create_quote
    from app.adapters.memory.memory import _get_connection
    
    # 1. Crear presupuesto
    res = await create_quote(
        client_name="Test Client",
        client_nif="12345678Z",
        amount=1000.0,
        concept="Servicio Test",
        is_draft=False
    )
    assert res["status"] == "ok"
    quote_id = res["quote_id"]
    
    # 2. Actualizar estado
    res_upd = await update_quote_status(quote_id, "aceptado")
    assert res_upd["status"] == "ok"
    
    # Verificar en DB
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM quotes WHERE id = (SELECT MAX(id) FROM quotes)")
        status = cursor.fetchone()["status"]
        assert status == "aceptado"
    finally:
        conn.close()
        
    # 3. Convertir a factura (Mocando generate_invoice_pdf para no generar un PDF real en la suite)
    from unittest.mock import AsyncMock
    with patch("app.tools.server.billing_tools.generate_invoice_pdf", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = {"status": "ok", "invoice_id": "F-TEST-001"}
        res_conv = await convert_quote_to_invoice(quote_id, confirmed_by_user=True)
        assert res_conv["status"] == "ok"
        mock_gen.assert_called_once()
        
        # Verificar estado actualizado a facturado
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM quotes WHERE id = (SELECT MAX(id) FROM quotes)")
            status = cursor.fetchone()["status"]
            assert status == "facturado"
        finally:
            conn.close()
