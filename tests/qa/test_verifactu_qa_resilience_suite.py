import pytest
import os
from unittest.mock import patch, MagicMock
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_db():
    VerifactuService.init_verifactu_schema()
    with _get_connection() as conn:
        conn.execute("DELETE FROM sif_event_log")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.commit()
    yield

def test_qa_worker_handles_403_without_endless_retry_loop():
    """QA: Comprueba que un error 403 no deja la factura en estado de reintento indefinido."""
    invoice_data = {
        "invoice_number": "QA-2026-0001",
        "date_of_issue": "20-08-2026",
        "issuer_nif": "99999972C",
        "receiver_nif": "B11111111",
        "total_amount": 121.0,
        "base_imponible": 100.0,
        "iva_amount": 21.0
    }
    
    # 1. Registrar factura localmente
    res = VerifactuService.register_invoice(invoice_data)
    assert res["status"] in ("success", "registered")

    # 2. Forzar que la factura esté marcada como PENDIENTE
    with _get_connection() as conn:
        conn.execute(
            "UPDATE verifactu_invoices SET delivery_status = 'PENDIENTE', retry_count = 0 WHERE invoice_number = 'QA-2026-0001'"
        )
        conn.commit()

    # 3. Simular respuesta 403 Forbidden en send_to_aeat_sif
    mock_403_response = {
        "status": "rejected",
        "delivery_status": "ERROR_AUTH",
        "code": 403,
        "error": "Acceso denegado (403 Forbidden)",
        "message": "Rechazo de autenticación mTLS por la AEAT (403 Forbidden)."
    }

    with patch.object(VerifactuService, "send_to_aeat_sif", return_value=mock_403_response):
        VerifactuService.process_pending_deliveries()

    # 4. Verificar que el estado en BD quedó como ERROR_AUTH
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT delivery_status, retry_count FROM verifactu_invoices WHERE invoice_number = 'QA-2026-0001'"
        ).fetchone()
        assert row["delivery_status"] == "ERROR_AUTH"
        assert row["retry_count"] == 1

    # 5. Volver a ejecutar process_pending_deliveries y comprobar que NO se reintenta innecesariamente
    with patch.object(VerifactuService, "send_to_aeat_sif") as mock_send:
        VerifactuService.process_pending_deliveries()
        assert not mock_send.called

def test_qa_event_log_chain_integrity_under_stress():
    """QA: Valida la resistencia y solidez de la cadena de hashes en sif_event_log tras 25 eventos secuenciales."""
    hashes = []
    for i in range(25):
        h = VerifactuService.log_sif_event(
            event_type=f"EVENT_TEST_{i}",
            description=f"Descripción de auditoría para evento #{i}"
        )
        hashes.append(h)

    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM sif_event_log ORDER BY id ASC").fetchall()
        assert len(rows) == 25

        for i, row in enumerate(rows):
            assert row["current_hash"] == hashes[i]
            if i == 0:
                assert row["prev_event_hash"] is None
            else:
                assert row["prev_event_hash"] == hashes[i - 1]
