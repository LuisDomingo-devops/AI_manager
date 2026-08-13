import pytest
from app.tools.server.billing_tools import create_quote, sign_quote, verify_quote_signature
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

@pytest.mark.asyncio
async def test_quote_digital_signature_flow():
    # 1. Limpiar base de datos
    from app.domain.services.verifactu_service import VerifactuService
    VerifactuService.init_verifactu_schema()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quotes")
        cursor.execute("DELETE FROM verifactu_invoices")
        conn.commit()
    finally:
        conn.close()

    # 2. Crear un presupuesto
    res_q = await create_quote(
        client_name="Cliente Firma Test",
        client_nif="12345678Z",
        amount=1200.0,
        concept="Auditoría de Sistemas",
        is_draft=False
    )
    assert res_q["status"] == "ok"
    quote_id = res_q["quote_id"]

    # 3. Intentar verificar antes de firmar (debe fallar/dar error de que no tiene firma)
    res_ver_init = await verify_quote_signature(quote_id=quote_id)
    assert res_ver_init["status"] == "error"
    assert "no posee ninguna firma digital" in res_ver_init["message"]

    # 4. Firmar el presupuesto
    res_sign = await sign_quote(quote_id=quote_id)
    assert res_sign["status"] == "ok"
    assert "firmado criptográficamente con éxito" in res_sign["message"]
    signature = res_sign["signature"]
    assert signature != ""

    # 5. Verificar firma válida
    res_ver = await verify_quote_signature(quote_id=quote_id)
    assert res_ver["status"] == "ok"
    assert res_ver["valid"] is True
    assert "VÁLIDA" in res_ver["message"]

    # 6. Alterar los datos en DB (Simular manipulación de datos)
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        # Modificar el importe total en la DB (cifrando un valor manipulado)
        manipulated_amount = encryptor.encrypt("9999.0")
        cursor.execute("UPDATE quotes SET total_amount = ?", (manipulated_amount,))
        conn.commit()
    finally:
        conn.close()

    # 7. Verificar de nuevo: la firma debe ser INVÁLIDA al no coincidir el hash
    res_ver_manipulated = await verify_quote_signature(quote_id=quote_id)
    assert res_ver_manipulated["status"] == "ok"
    assert res_ver_manipulated["valid"] is False
    assert "INVÁLIDA" in res_ver_manipulated["message"]
