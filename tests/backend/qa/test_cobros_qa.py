import pytest
from app.domain.services.collection_service import CollectionService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection

def test_cobros_qa_flujo_completo():
    """
    Test QA End-to-End: Conciliación de facturas y cobros manual/automática.
    """
    # Flujo QA E2E
    # 1. Sistema recibe nueva factura
    invoice_data = {
        "invoice_id": "inv_qa_cobro",
        "date": "2026-09-07",
        "issuer_name": "QA Corp",
        "issuer_nif": "00000000Q",
        "receiver_name": "Cliente QA",
        "receiver_nif": "99999999Q",
        "base_imponible": 500.0,
        "iva_rate": 21.0,
        "iva_amount": 105.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 605.0,
        "status": "emitida",
        "quarter": 3,
        "year": 2026,
        "category": "ingreso"
    }
    InvoiceRepository.save(invoice_data)
    
    # 2. Usuario registra primer pago parcial (anticipo)
    res1 = CollectionService.register_payment("inv_qa_cobro", 200.0, "transferencia", "2026-09-08", "Anticipo")
    assert res1["status"] == "ok"
    assert res1["outstanding_balance"] == 405.0
    
    # 3. Validar estado (sigue siendo emitida/parcial)
    inv1 = InvoiceRepository.find_invoice_by_id("inv_qa_cobro")
    assert inv1["status"] != "cobrada"
    
    # 4. Usuario registra pago final
    res2 = CollectionService.register_payment("inv_qa_cobro", 405.0, "transferencia", "2026-09-10", "Liquidacion")
    assert res2["status"] == "ok"
    assert res2["outstanding_balance"] == 0.0
    
    # 5. Validar estado final = cobrada
    inv2 = InvoiceRepository.find_invoice_by_id("inv_qa_cobro")
    assert inv2["status"] == "cobrada"
    
    # Limpiar BD
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM payments WHERE invoice_id = 'inv_qa_cobro'")
    cursor.execute("DELETE FROM invoices")
    conn.commit()
    conn.close()
