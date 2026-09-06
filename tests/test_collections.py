import pytest
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.tools.server.billing_tools import register_payment, get_invoice_payment_summary

@pytest.mark.asyncio
async def test_collections():
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        
        import uuid
        test_invoice_id = f"F-COLLECTION-TEST-{uuid.uuid4().hex[:6]}"
        total_amount = 121.0
        
        cursor.execute("""
            INSERT INTO invoices (invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount, category, year, status, concept)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            encryptor.encrypt(test_invoice_id),
            encryptor.encrypt("01/01/2026"),
            encryptor.encrypt("Test Issuer"),
            encryptor.encrypt("11111111A"),
            encryptor.encrypt("Test Receiver"),
            encryptor.encrypt("22222222B"),
            encryptor.encrypt("100.0"),
            encryptor.encrypt("21.0"),
            encryptor.encrypt("21.0"),
            encryptor.encrypt("0.0"),
            encryptor.encrypt("0.0"),
            encryptor.encrypt("121.0"),
            "income", 2026, "firmada",
            encryptor.encrypt("Test Concept")
        ))
        conn.commit()
    finally:
        conn.close()

    # Register partial payment
    res = await register_payment(test_invoice_id, 50.0, "transferencia", "A cuenta")
    assert res["status"] == "ok", res.get("message", str(res))
    assert res["pending_balance"] == 71.0
    
    summary = await get_invoice_payment_summary(test_invoice_id)
    assert summary["status"] == "ok"
    assert summary["pending_balance"] == 71.0
    assert summary["total_paid"] == 50.0
    
    # Register remaining payment
    res2 = await register_payment(test_invoice_id, 71.0, "efectivo", "Resto")
    assert res2["status"] == "ok"
    assert res2["pending_balance"] == 0.0
    
    # Check status updated to cobrada
    summary2 = await get_invoice_payment_summary(test_invoice_id)
    assert summary2["pending_balance"] == 0.0
    assert summary2["total_paid"] == 121.0
    
    # Verify invoice status
    from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
    inv = InvoiceRepository.find_invoice_by_id(test_invoice_id)
    assert inv is not None
    assert inv["status"] == "cobrada"
