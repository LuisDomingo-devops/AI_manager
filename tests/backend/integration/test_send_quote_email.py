import pytest
from unittest.mock import patch, MagicMock
from app.tools.server.billing_tools import create_quote, send_quote_email
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
@patch("app.tools.server.mail_tools.mail_send_email")
async def test_send_quote_email_flow(mock_mail):
    # Mocking mail sender response
    mock_mail.return_value = {"status": "ok", "message": "Email sent"}

    # 1. Limpiar base de datos
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM quotes")
        conn.commit()
    finally:
        conn.close()

    # 2. Crear un presupuesto
    res_q = await create_quote(
        client_name="Cliente Envio Email Test",
        client_nif="12345678Z",
        amount=500.0,
        concept="Servicios de Asesoramiento",
        is_draft=False
    )
    assert res_q["status"] == "ok"
    quote_id = res_q["quote_id"]

    # 3. Intentar enviar por correo
    res_send = await send_quote_email(quote_id=quote_id, recipient_email="cliente@correo.com")
    assert res_send["status"] == "ok"
    assert "enviado por correo electrónico" in res_send["message"]

    # Verificar que mail_send_email fue invocado con el destinatario y la ruta correcta
    mock_mail.assert_called_once()
    args, kwargs = mock_mail.call_args
    assert kwargs["recipient"] == "cliente@correo.com"
    assert quote_id in kwargs["subject"]
    assert "Servicios de Asesoramiento" in kwargs["body"] or "Presupuesto" in kwargs["body"]

    # 4. Intentar enviar presupuesto inexistente
    res_fail = await send_quote_email(quote_id="P-NONEXISTENT", recipient_email="cliente@correo.com")
    assert res_fail["status"] == "error"
    assert "No se encontró el archivo físico" in res_fail["message"]
