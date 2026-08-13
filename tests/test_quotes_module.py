import pytest
import os
from pathlib import Path
from app.tools.server.billing_tools import create_quote, get_quotes, convert_quote_to_invoice
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
async def test_quotes_flow():
    # 1. Limpiar base de datos para pruebas
    from app.domain.services.verifactu_service import VerifactuService
    VerifactuService.init_verifactu_schema()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quotes")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM verifactu_invoices")
        conn.commit()
    finally:
        conn.close()

    # 2. Crear un presupuesto Borrador
    res = await create_quote(
        client_name="Cliente Presupuesto Test",
        client_nif="12345678Z",
        amount=1000.0,
        concept="Desarrollo de Software Alfonso",
        iva_rate=21.0,
        irpf_rate=15.0,
        is_draft=True
    )
    assert res["status"] == "ok"
    quote_id = res["quote_id"]
    file_path = res["file_path"]

    # Verificar que el PDF existe físicamente
    assert os.path.exists(file_path) is True

    # 3. Listar y verificar datos descifrados
    res_list = await get_quotes()
    assert res_list["status"] == "ok"
    quotes = res_list["quotes"]
    assert len(quotes) == 1
    q = quotes[0]
    assert q["quote_id"] == quote_id
    assert q["client_name"] == "Cliente Presupuesto Test"
    assert q["client_nif"] == "12345678Z"
    assert q["base_imponible"] == 1000.0
    assert q["iva_rate"] == 21.0
    assert q["iva_amount"] == 210.0
    assert q["irpf_rate"] == 15.0
    assert q["irpf_amount"] == 150.0
    assert q["total_amount"] == 1060.0
    assert q["concept"] == "Desarrollo de Software Alfonso"
    assert q["status"] == "borrador"

    # 4. Convertir a factura
    res_conv = await convert_quote_to_invoice(quote_id=quote_id, confirmed_by_user=True)
    assert res_conv["status"] == "ok"
    invoice_id = res_conv["invoice_id"]

    # Verificar que la factura se generó en la base de datos de facturas
    from app.tools.server.billing_tools import get_clients # para verificar base o simplemente querying invoices
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, invoice_id, total_amount, status FROM invoices")
        row = cursor.fetchone()
        assert row is not None
        from app.utils.encryption import encryptor
        dec_inv_id = encryptor.decrypt(row["invoice_id"])
        assert dec_inv_id == invoice_id
        # Como es firme, status es firmada
        assert row["status"] == "firmada"
    finally:
        conn.close()

    # Verificar que el presupuesto cambió de estado a 'facturado'
    res_list_2 = await get_quotes()
    assert res_list_2["quotes"][0]["status"] == "facturado"

    # 5. Intentar convertir un presupuesto que ya no existe
    res_fail = await convert_quote_to_invoice(quote_id="P-NONEXISTENT")
    assert res_fail["status"] == "error"

    # Limpiar PDFs de prueba generados
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception:
        pass
