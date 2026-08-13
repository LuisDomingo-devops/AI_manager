import pytest
from unittest.mock import patch, MagicMock
from app.tools.server.billing_tools import (
    generate_invoice_pdf, register_payment, get_invoice_payment_summary,
    get_pending_payments_report, send_payment_reminder_email
)
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

@pytest.mark.asyncio
@patch("app.tools.server.mail_tools.mail_send_email")
async def test_payments_flow(mock_mail):
    mock_mail.return_value = {"status": "ok", "message": "Email sent"}

    # 1. Limpiar base de datos
    from app.domain.services.verifactu_service import VerifactuService
    VerifactuService.init_verifactu_schema()
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM payments")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM verifactu_invoices")
        conn.commit()
    finally:
        conn.close()

    # 2. Crear una factura de venta de 1000 EUR
    # Con IVA 21% e IRPF 15%, el total a cobrar es 1060 EUR
    res_inv = await generate_invoice_pdf(
        client_name="Cliente Pagos Test",
        client_nif="12345678Z",
        amount=1000.0,
        concept="Desarrollo de Modulo de Pagos",
        iva_rate=21.0,
        irpf_rate=15.0,
        confirmed_by_user=True
    )
    assert res_inv["status"] == "ok"
    invoice_id = res_inv["invoice_id"]
    invoice_total = 1060.0 # 1000 + 210 (IVA) - 150 (IRPF)

    # 3. Registrar primer pago parcial de 400 EUR
    res_p1 = await register_payment(invoice_id=invoice_id, amount=400.0, payment_method="tarjeta", notes="Primer pago parcial")
    assert res_p1["status"] == "ok"
    assert res_p1["total_paid"] == 400.0
    assert res_p1["pending_balance"] == 660.0 # 1060 - 400 = 660
    assert res_p1["status_factura"] == "firmada" # Sigue firmada/pendiente

    # 4. Comprobar reporte de cobros pendientes (debe aparecer nuestra factura)
    rep_pending = await get_pending_payments_report()
    assert rep_pending["status"] == "ok"
    pending_list = rep_pending["pending_invoices"]
    assert len(pending_list) == 1
    assert pending_list[0]["invoice_id"] == invoice_id
    assert pending_list[0]["pending_balance"] == 660.0

    # 5. Enviar recordatorio de pago
    res_rem = await send_payment_reminder_email(invoice_id=invoice_id)
    assert res_rem["status"] == "ok"
    mock_mail.assert_called_once()

    # 6. Registrar segundo pago para liquidar el saldo de 660 EUR
    res_p2 = await register_payment(invoice_id=invoice_id, amount=660.0, payment_method="transferencia", notes="Pago final liquidado")
    assert res_p2["status"] == "ok"
    assert res_p2["total_paid"] == 1060.0
    assert res_p2["pending_balance"] == 0.0
    assert res_p2["status_factura"] == "cobrada"

    # 7. Comprobar resumen de cobros de la factura
    summary = await get_invoice_payment_summary(invoice_id=invoice_id)
    assert summary["status"] == "ok"
    assert summary["total_paid"] == 1060.0
    assert summary["pending_balance"] == 0.0
    assert len(summary["payments"]) == 2

    # 8. Comprobar reporte de cobros pendientes (debe estar vacío ahora)
    rep_pending_after = await get_pending_payments_report()
    assert len(rep_pending_after["pending_invoices"]) == 0
