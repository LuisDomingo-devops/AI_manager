import pytest
from pathlib import Path
from lxml import etree
import signxml

from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_verifactu_db(tmp_path, monkeypatch):
    import sys
    import app.adapters.memory.memory
    memory_module = sys.modules["app.adapters.memory.memory"]
    test_db = tmp_path / "memory_test_verifactu_anulacion.db"
    monkeypatch.setattr(memory_module, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()

def test_invoice_cancellation_flow():
    # 1. Registrar una factura firme normal
    invoice = {
        "invoice_number": "FAC-ANUL-001",
        "date_of_issue": "2026-08-07",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    res_alta = VerifactuService.register_invoice(invoice)
    assert res_alta["status"] == "success"
    hash_alta = res_alta["current_hash"]
    
    # 2. Anular la factura
    res_anul = VerifactuService.cancel_invoice("FAC-ANUL-001")
    assert res_anul["status"] == "success"
    
    # 3. Comprobar que en la base de datos hay una nueva fila de anulación y apunta al hash anterior
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM verifactu_invoices ORDER BY id ASC").fetchall()
        assert len(rows) == 2
        
        # Fila de Alta
        assert rows[0]["invoice_number"] == "FAC-ANUL-001"
        assert rows[0]["status"] == "ANULADA"
        
        # Fila de Anulación
        assert rows[1]["invoice_number"] == "FAC-ANUL-001_ANUL"
        assert rows[1]["status"] == "ANULADA"
        assert rows[1]["prev_hash"] == hash_alta
        
    # 4. Validar el XML de anulación generado
    xml_dir = Path(__file__).resolve().parents[1] / "data" / "xml_invoices"
    xml_file = xml_dir / "FAC-ANUL-001_anulacion_verifactu.xml"
    assert xml_file.exists()
    
    xml_content = xml_file.read_text(encoding="utf-8")
    root = etree.fromstring(xml_content.encode("utf-8"))
    
    # Debe ser RegFactuSistemaFacturacion
    assert root.tag == "RegFactuSistemaFacturacion"
    
    # Debe contener RegistroFacturacionAnulacion en lugar de RegistroFacturacionAlta
    reg_anul = root.find("RegistroFacturacionAnulacion")
    assert reg_anul is not None
    
    # Debe tener el IDFacturaAnulada correcto
    id_factura = reg_anul.find("IDFacturaAnulada")
    assert id_factura.find("NumSerieFacturaEmisor").text == "FAC-ANUL-001"
    
    # Comprobar la integridad de la cadena
    audit = VerifactuService.verify_chain_integrity()
    assert audit["status"] == "valid"

def test_cancel_non_existent_or_already_canceled_invoice():
    res = VerifactuService.cancel_invoice("FAC-NO-EXISTE")
    assert res["status"] == "error"
    assert "no encontrada" in res["message"]
    
    # Intentar anular dos veces
    invoice = {
        "invoice_number": "FAC-ANUL-DUPL",
        "date_of_issue": "2026-08-07",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    VerifactuService.register_invoice(invoice)
    
    # Primera anulación
    assert VerifactuService.cancel_invoice("FAC-ANUL-DUPL")["status"] == "success"
    # Segunda anulación -> debe fallar
    res_double = VerifactuService.cancel_invoice("FAC-ANUL-DUPL")
    assert res_double["status"] == "error"
    assert "no encontrada o ya anulada" in res_double["message"]
