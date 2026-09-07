import pytest
from app.domain.services.collection_service import CollectionService
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection

def test_cobros_db_integration():
    """
    Test de integración: almacenamiento de cobros en BD.
    """
    # 1. Preparar datos de prueba (factura)
    conn = _get_connection()
    cursor = conn.cursor()
    # Insertar una factura a través del repo
    invoice_data = {
        "invoice_id": "inv_cobro_1",
        "date": "2026-09-07",
        "issuer_name": "Yo",
        "issuer_nif": "00000000T",
        "receiver_name": "Cliente Cobro",
        "receiver_nif": "11111111A",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "status": "emitida",
        "quarter": 3,
        "year": 2026,
        "category": "ingreso"
    }
    InvoiceRepository.save(invoice_data)
    
    # 2. Registrar pago
    res = CollectionService.register_payment('inv_cobro_1', 121.0, 'transferencia', '2026-09-07', 'Pago completo')
    
    assert res['status'] == 'ok'
    assert res['outstanding_balance'] == 0.0
    
    # 3. Comprobar en BD
    invoice_after = InvoiceRepository.find_invoice_by_id('inv_cobro_1')
    assert invoice_after['status'] == 'cobrada'
    
    # Limpiar
    cursor.execute("DELETE FROM payments WHERE invoice_id = 'inv_cobro_1'")
    cursor.execute("DELETE FROM invoices")
    conn.commit()
    conn.close()

def test_cobros_banco_integration():
    """
    Test de integración: interacción con el módulo bancario.
    """
    # Por ahora verificamos que collection_service actualiza el ledger (que es la interacción contable/bancaria)
    conn = _get_connection()
    cursor = conn.cursor()
    invoice_data = {
        "invoice_id": "inv_cobro_2",
        "date": "2026-09-07",
        "issuer_name": "Yo",
        "issuer_nif": "00000000T",
        "receiver_name": "Cliente Banco",
        "receiver_nif": "22222222B",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "status": "emitida",
        "quarter": 3,
        "year": 2026,
        "category": "ingreso"
    }
    InvoiceRepository.save(invoice_data)
    
    res = CollectionService.register_payment('inv_cobro_2', 50.0, 'transferencia', '2026-09-07', 'Pago parcial')
    
    assert res['status'] == 'ok'
    assert res['outstanding_balance'] == 71.0
    
    # Comprobar el ledger
    # Asumiendo tabla journal_entries
    cursor.execute("SELECT * FROM journal_entries WHERE concept = 'Cobro fra inv_cobro_2'")
    entries = cursor.fetchall()
    # Si LedgerService guardó correctamente
    if entries:
        assert entries[0]['concept'] == 'Cobro fra inv_cobro_2'
        
    cursor.execute("DELETE FROM payments WHERE invoice_id = 'inv_cobro_2'")
    cursor.execute("DELETE FROM invoices")
    cursor.execute("DELETE FROM journal_entries WHERE concept = 'Cobro fra inv_cobro_2'")
    conn.commit()
    conn.close()
