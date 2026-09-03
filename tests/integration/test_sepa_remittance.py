import pytest
import xml.etree.ElementTree as ET
from app.domain.services.sepa_service import SepaService
from app.adapters.memory.memory import _get_connection

def test_sepa_remittance_generation():
    # 1. Preparar base de datos
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_transfers")
        cursor.execute("DELETE FROM bank_connections")
        cursor.execute("DELETE FROM user_profile")
        
        # Emisor
        cursor.execute("INSERT INTO user_profile (user_type, nif, razon_social) VALUES ('autonomo', '12345678Z', 'Empresa Test')")
        
        # Cuenta bancaria activa y por defecto
        cursor.execute("INSERT INTO bank_connections (alias, provider, bank_name, iban, status, is_default_remittance) VALUES ('Mi Banco', 'mock', 'Banco Test', 'ES1234567890123456789012', 'active', 1)")
        
        # Pagos pendientes
        cursor.execute("INSERT INTO bank_transfers (transfer_date, recipient_name, recipient_iban, amount, concept, status) VALUES ('2026-09-03', 'Proveedor 1', 'ES9876543210987654321098', 150.50, 'Factura A', 'initiated')")
        cursor.execute("INSERT INTO bank_transfers (transfer_date, recipient_name, recipient_iban, amount, concept, status) VALUES ('2026-09-03', 'Proveedor 2', 'ES1111111111111111111111', 50.00, 'Factura B', 'initiated')")
        conn.commit()
    finally:
        conn.close()

    # 2. Generar XML
    res = SepaService.generate_remittance_xml()
    
    assert res["status"] == "ok"
    assert res["total_sum"] == 200.50
    assert len(res["transfer_ids"]) == 2
    
    xml_content = res["xml_content"]
    assert "pain.001.001.03" in xml_content
    assert "ES1234567890123456789012" in xml_content
    assert "ES9876543210987654321098" in xml_content
    assert "150.50" in xml_content
    
    # 3. Validar parseo XML básico
    root = ET.fromstring(xml_content)
    assert root.tag.endswith("Document")

    # 4. Verificar que se marcaron como emitidos
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM bank_transfers")
        statuses = [r["status"] for r in cursor.fetchall()]
        assert all(s == "remitted" for s in statuses)
    finally:
        conn.close()
