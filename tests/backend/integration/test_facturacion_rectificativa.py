import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_verifactu_db(tmp_path, monkeypatch):
    import sys
    import app.infrastructure.database.memory.memory
    memory_module = sys.modules["app.infrastructure.database.memory.memory"]
    test_db = tmp_path / "memory_test_rectificativa.db"
    monkeypatch.setattr(memory_module, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_sif")
        conn.execute("DELETE FROM sif_event_log")
        conn.commit()

        # Insert test cert to prevent ValueError
        from app.utils.encryption import encryptor
        try:
            with open("data/certificados_prueba/certificado_pruebas.pem", "r") as f_cert:
                cert_data = f_cert.read()
            with open("data/certificados_prueba/clave_pruebas.pem", "r") as f_key:
                key_data = f_key.read()
            enc_data = encryptor.encrypt(cert_data + "\n" + key_data)
            conn.execute(
                "INSERT INTO certificates (id, tenant_id, cert_type, encrypted_p12, subject_name) "
                "VALUES ('test-cert', 'default', 'AEAT_PRUEBA', ?, 'Pruebas AEAT')",
                (enc_data,)
            )
            conn.commit()
        except FileNotFoundError:
            pass

    yield
    with _get_connection() as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_sif")
        conn.execute("DELETE FROM sif_event_log")
        conn.execute("DELETE FROM certificates")
        conn.commit()

def test_register_invoice_rectificativa_xml_structure(clean_verifactu_db):
    invoice_data = {
        "invoice_number": "R-2026-001",
        "date_of_issue": "20-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "00000000T",
        "base_imponible": -100.0,
        "iva_amount": -21.0,
        "total_amount": -121.0,
        "iva_rate": 21.0,
        "tipo_factura": "R1",
        "tipo_rectificativa": "I",
        "rectified_invoice_number": "F2026-101",
        "rectified_invoice_date": "19-08-2026"
    }

    mock_aeat_resp = {
        "status": "accepted",
        "delivery_status": "ACEPTADO",
        "csv": "AEAT-REAL-CSV-RECTIFICATIVA",
        "error_code": None,
        "error_desc": None,
        "raw_response": "<xml>Mocked AEAT Accepted</xml>"
    }

    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_aeat_resp) as mock_send:
        res = VerifactuService.register_invoice(invoice_data)
        assert res["status"] == "success"

        # Verify the XML that was sent contains Rectificativa fields
        xml_sent = mock_send.call_args[0][0]
        assert "<TipoFactura>R1</TipoFactura>" in xml_sent
        assert "<TipoRectificativa>I</TipoRectificativa>" in xml_sent
        assert "<FacturasRectificadas>" in xml_sent
        assert "<NumSerieFacturaEmisor>F2026-101</NumSerieFacturaEmisor>" in xml_sent

def test_cancel_invoice_xml_structure(clean_verifactu_db):
    # First register an invoice
    invoice_data = {
        "invoice_number": "F2026-200",
        "date_of_issue": "20-08-2026",
        "issuer_nif": "12345678Z",
        "receiver_nif": "00000000T",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0,
        "iva_rate": 21.0,
        "tipo_factura": "F1"
    }
    
    mock_aeat_resp = {
        "status": "accepted",
        "delivery_status": "ACEPTADO",
        "csv": "AEAT-CSV-200"
    }
    
    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_aeat_resp):
        VerifactuService.register_invoice(invoice_data)
        
    # Then cancel it
    mock_cancel_resp = {
        "status": "accepted",
        "delivery_status": "ACEPTADO",
        "csv": "AEAT-CSV-CANCEL-200"
    }
    
    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_cancel_resp) as mock_cancel:
        res = VerifactuService.cancel_invoice("F2026-200")
        assert res["status"] == "success"
        
        xml_sent = mock_cancel.call_args[0][0]
        assert "<RegistroFacturacionAnulacion>" in xml_sent
        assert "<IDFacturaAnulada>" in xml_sent
        assert "<NumSerieFacturaEmisor>F2026-200</NumSerieFacturaEmisor>" in xml_sent
