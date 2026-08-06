import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from lxml import etree
import signxml

from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_verifactu_db(tmp_path, monkeypatch):
    import app.adapters.memory.memory as memory
    test_db = tmp_path / "memory_test_verifactu_integrity.db"
    monkeypatch.setattr(memory, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()

def test_xml_structure_xsd_compliance():
    # 1. Registrar una factura firme
    invoice = {
        "invoice_number": "FAC-XSD-0001",
        "date_of_issue": "2026-08-05",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    res = VerifactuService.register_invoice(invoice)
    assert res["status"] == "success"
    
    # 2. Localizar el archivo XML generado
    xml_dir = Path(__file__).resolve().parents[1] / "data" / "xml_invoices"
    xml_file = xml_dir / "FAC-XSD-0001_verifactu.xml"
    assert xml_file.exists()
    
    # 3. Validar estructura del XML contra los elementos requeridos
    xml_content = xml_file.read_text(encoding="utf-8")
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser=parser)
    
    # Debe ser SuministroLRRegistroFacturacionAlta
    assert root.tag == "SuministroLRRegistroFacturacionAlta"
    
    # Debe contener Cabecera y RegistroFacturacionAlta
    cabecera = root.find("Cabecera")
    reg_alta = root.find("RegistroFacturacionAlta")
    assert cabecera is not None
    assert reg_alta is not None
    
    # Validar SistemaInformatico oficial
    sistema = reg_alta.find("SistemaInformatico")
    assert sistema is not None
    assert sistema.find("Nombre").text == "Alfonso Autónomo SIF"
    assert sistema.find("Version").text == "2.0.0"
    
    # Validar que está firmado usando XMLDSig
    ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
    signature = root.find(".//ds:Signature", namespaces=ns)
    assert signature is not None

def test_chain_propagation_corruption():
    # Registrar 3 facturas seguidas
    hashes = []
    for i in range(1, 4):
        inv = {
            "invoice_number": f"FAC-PROP-000{i}",
            "date_of_issue": f"2026-08-0{i}",
            "issuer_nif": "12345678Z",
            "receiver_nif": "87654321A",
            "base_imponible": 100.0,
            "iva_amount": 21.0,
            "total_amount": 121.0
        }
        res = VerifactuService.register_invoice(inv)
        hashes.append(res["current_hash"])
        
    # La cadena debe ser válida inicialmente
    assert VerifactuService.verify_chain_integrity()["status"] == "valid"
    
    # Corromper deliberadamente la factura del medio (2ª factura)
    with _get_connection() as conn:
        conn.execute(
            "UPDATE verifactu_invoices SET base_imponible = 99.0 WHERE invoice_number = 'FAC-PROP-0002'"
        )
        conn.commit()
        
    # Verificar integridad: debe detectar la rotura
    audit = VerifactuService.verify_chain_integrity()
    assert audit["status"] in ("tampered", "corrupted")
    # Debe señalar a la factura 2 como el punto de rotura/corrupción
    assert audit["corrupted_invoice_number"] == "FAC-PROP-0002"

def test_send_to_aeat_sif_mtls_failure():
    # Simular una respuesta fallida de la AEAT (mTLS o servidor caído)
    with patch("httpx.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.post.return_value = MagicMock(status_code=500, text="Internal Server Error")
        mock_client.return_value.__enter__.return_value = mock_instance
        
        # Con certificados de prueba configurados en el entorno
        with patch.dict("os.environ", {
            "ALFONSO_AEAT_CERT": "dummy_cert.pem",
            "ALFONSO_AEAT_KEY": "dummy_key.pem"
        }), patch("os.path.exists", return_value=True):
            
            resp = VerifactuService.send_to_aeat_sif("<xml></xml>")
            assert resp["status"] == "rejected"
            assert resp["code"] == 500
            assert "Internal Server Error" in resp["error"]

def test_sanitize_malformed_nif():
    # Registrar factura con NIF con espacios o caracteres extraños
    invoice = {
        "invoice_number": "FAC-NIF-CLEAN",
        "date_of_issue": "2026-08-05",
        "issuer_nif": " 12345678z ", # Espacios y minúsculas
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    res = VerifactuService.register_invoice(invoice)
    assert res["status"] == "success"
    
    # Comprobar que en la base de datos se normalizó a mayúsculas y sin espacios
    with _get_connection() as conn:
        row = conn.execute("SELECT issuer_nif FROM verifactu_invoices WHERE invoice_number = 'FAC-NIF-CLEAN'").fetchone()
        assert row["issuer_nif"] == "12345678Z"
