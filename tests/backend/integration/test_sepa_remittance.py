import pytest
from app.domain.services.sepa_service import SepaService
from app.adapters.memory.memory import _get_connection
import xml.etree.ElementTree as ET

def test_generate_remittance_success():
    # Arrange: Preparar bbdd
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Limpiar
        cursor.execute("DELETE FROM invoices")
        
        # Insertar cuenta activa (si no hay)
        cursor.execute("INSERT OR IGNORE INTO bank_connections (id, iban, bank_name, status) VALUES (99, 'ES0000000000000000000000', 'TestBank', 'active')")
        
        # Insertar invoices pendientes con IBAN
        cursor.execute("INSERT INTO invoices (invoice_number, date_of_issue, issuer_nif, receiver_nif, base_imponible, iva_amount, total_amount, current_hash, status, client_name, client_iban) VALUES ('FRA-01', '2026-09-03', '123', '456', 100, 21, 121, 'hash1', 'emitida', 'Cliente 1', 'ES9876543210987654321098')")
        cursor.execute("INSERT INTO invoices (invoice_number, date_of_issue, issuer_nif, receiver_nif, base_imponible, iva_amount, total_amount, current_hash, status, client_name, client_iban) VALUES ('FRA-02', '2026-09-03', '123', '456', 50, 10.5, 60.5, 'hash2', 'emitida', 'Cliente 2', 'ES1111111111111111111111')")
        conn.commit()

    # Act
    res = SepaService.generate_remittance_xml()
    
    # Assert
    assert res["status"] == "ok"
    assert "xml_content" in res
    assert len(res["transfer_ids"]) == 2
    assert res["total_sum"] == 181.5

    # Validar XML generado
    root = ET.fromstring(res["xml_content"])
    assert "Document" in root.tag
