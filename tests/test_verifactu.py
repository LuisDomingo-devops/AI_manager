import pytest
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_db(tmp_path, monkeypatch):
    import app.adapters.memory.memory as memory
    test_db = tmp_path / "memory_test_verifactu.db"
    monkeypatch.setattr(memory, "DB_PATH", test_db)
    
    # Limpiar tabla verifactu antes de cada test
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()
    yield

def test_verifactu_registration_and_chaining():
    invoice1 = {
        "invoice_number": "FAC-2026-0001",
        "date_of_issue": "2026-08-01",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    # Registrar primera factura
    res1 = VerifactuService.register_invoice(invoice1)
    assert res1["status"] == "success"
    assert res1["prev_hash"] is None
    h1 = res1["current_hash"]
    
    invoice2 = {
        "invoice_number": "FAC-2026-0002",
        "date_of_issue": "2026-08-02",
        "issuer_nif": "12345678Z",
        "receiver_nif": "44555666B",
        "base_imponible": 200.0,
        "iva_amount": 42.0,
        "total_amount": 242.0
    }
    
    # Registrar segunda factura
    res2 = VerifactuService.register_invoice(invoice2)
    assert res2["status"] == "success"
    assert res2["prev_hash"] == h1
    h2 = res2["current_hash"]
    
    # Verificar integridad de la cadena
    integrity = VerifactuService.verify_chain_integrity()
    assert integrity["status"] == "valid"

def test_verifactu_chain_corruption():
    invoice1 = {
        "invoice_number": "FAC-2026-0001",
        "date_of_issue": "2026-08-01",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    VerifactuService.register_invoice(invoice1)
    
    invoice2 = {
        "invoice_number": "FAC-2026-0002",
        "date_of_issue": "2026-08-02",
        "issuer_nif": "12345678Z",
        "receiver_nif": "44555666B",
        "base_imponible": 200.0,
        "iva_amount": 42.0,
        "total_amount": 242.0
    }
    VerifactuService.register_invoice(invoice2)
    
    # Corromper deliberadamente la base de datos
    with _get_connection() as conn:
        conn.execute(
            "UPDATE verifactu_invoices SET total_amount = 999.0 WHERE invoice_number = 'FAC-2026-0001'"
        )
        conn.commit()
        
    # Verificar integridad de la cadena debe reportar alteración
    integrity = VerifactuService.verify_chain_integrity()
    assert integrity["status"] in ("tampered", "corrupted")

def test_sif_event_logging():
    # Limpiar tabla sif_event_log antes de probar
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS sif_event_log")
        conn.commit()

    h1 = VerifactuService.log_sif_event("SYSTEM_START", "El sistema informático de facturación Alfonso ha iniciado.")
    assert h1 is not None
    
    h2 = VerifactuService.log_sif_event("DB_BACKUP", "Copia de seguridad realizada con éxito.")
    assert h2 is not None
    
    # Comprobar que se ha encadenado el hash
    with _get_connection() as conn:
        row = conn.execute("SELECT prev_event_hash FROM sif_event_log ORDER BY id DESC LIMIT 1").fetchone()
        assert row["prev_event_hash"] == h1

def test_facturae_export():
    invoice = {
        "invoice_number": "FAC-2026-B2G",
        "date_of_issue": "2026-08-05",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 500.00,
        "iva_amount": 105.00,
        "total_amount": 605.00
    }
    xml_str = VerifactuService.export_to_facturae_xml(invoice)
    assert xml_str is not None
    assert "<Facturae" in xml_str
    assert "Signature" in xml_str  # Asegurar que incluye la firma XMLDSig con namespace ds:Signature



