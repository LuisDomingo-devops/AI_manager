import time
import pytest
import threading
from pathlib import Path
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_verifactu_db(tmp_path, monkeypatch):
    import app.adapters.memory.memory as memory
    test_db = tmp_path / "memory_test_verifactu_qa_stress.db"
    monkeypatch.setattr(memory, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.execute("DROP TABLE IF EXISTS sif_event_log")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.execute("DROP TABLE IF EXISTS sif_event_log")
        conn.commit()

def test_concurrent_invoice_chaining():
    # Simular 10 facturas generadas de manera concurrente
    errors = []
    
    def register_worker(worker_id):
        try:
            # Añadir un delay leve para forzar concurrencia y comprobar que el bloqueo de SQLite se comporta de forma segura
            time.sleep(0.05 * worker_id)
            invoice = {
                "invoice_number": f"FAC-CONC-{worker_id:04d}",
                "date_of_issue": "2026-08-06",
                "issuer_nif": "12345678Z",
                "receiver_nif": "87654321A",
                "base_imponible": 100.0 * worker_id,
                "iva_amount": 21.0 * worker_id,
                "total_amount": 121.0 * worker_id
            }
            res = VerifactuService.register_invoice(invoice)
            assert res["status"] == "success"
        except Exception as e:
            errors.append(e)

    threads = []
    for i in range(1, 11):
        t = threading.Thread(target=register_worker, args=(i,))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # No debe haber errores por bloqueos de SQLite ni condiciones de carrera
    assert len(errors) == 0
    
    # Comprobar que todos los registros se insertaron y que la cadena de hashes de integridad es perfectamente válida
    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as cnt FROM verifactu_invoices").fetchone()["cnt"]
        assert count == 10
        
    audit = VerifactuService.verify_chain_integrity()
    assert audit["status"] == "valid"

def test_sif_event_log_recovery():
    # Loggear 3 eventos seguidos para verificar la cadena de eventos del SIF
    h1 = VerifactuService.log_sif_event("START", "Primer evento")
    h2 = VerifactuService.log_sif_event("RUN", "Segundo evento")
    h3 = VerifactuService.log_sif_event("STOP", "Tercer evento")
    
    # Validar integridad en base de datos
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM sif_event_log ORDER BY id ASC").fetchall()
        assert len(rows) == 3
        
        # El segundo apunta al primero
        assert rows[1]["prev_event_hash"] == h1
        # El tercero apunta al segundo
        assert rows[2]["prev_event_hash"] == h2

def test_non_ascii_characters_resilience():
    # Registrar una factura con caracteres no ASCII
    invoice = {
        "invoice_number": "FAC-Ñ-2026",
        "date_of_issue": "2026-08-06",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    res = VerifactuService.register_invoice(invoice)
    assert res["status"] == "success"
    
    # Verificar que el archivo XML se escribió en disco usando codificación utf-8 correctamente sin fallar
    xml_dir = Path(__file__).resolve().parents[1] / "data" / "xml_invoices"
    xml_file = xml_dir / "FAC-Ñ-2026_verifactu.xml"
    assert xml_file.exists()
    
    # No debe dar UnicodeDecodeError al leer el XML
    content = xml_file.read_text(encoding="utf-8")
    assert "FAC-Ñ-2026" in content
