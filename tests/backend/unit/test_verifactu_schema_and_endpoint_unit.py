import pytest
import sqlite3
import os
from unittest.mock import patch, MagicMock
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection
from app.config import settings

@pytest.fixture(autouse=True)
def clean_db():

    with _get_connection() as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_sif")
        conn.execute("DELETE FROM sif_event_log")
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_delete_verifactu")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.commit()
    yield

def test_sif_event_logging_schema_has_current_hash():
    """Verifica que log_sif_event calcula y almacena current_hash y prev_event_hash correctamente."""
    h1 = VerifactuService.log_sif_event("STARTUP_SYSTEM", "Arranque inicial de pruebas")
    assert h1 is not None
    assert len(h1) == 64

    with _get_connection() as conn:
        row1 = conn.execute("SELECT * FROM sif_event_log WHERE current_hash = ?", (h1,)).fetchone()
        assert row1 is not None
        assert row1["event_type"] == "STARTUP_SYSTEM"
        assert row1["description"] == "Arranque inicial de pruebas"
        assert row1["current_hash"] == h1
        assert row1["prev_event_hash"] is None
        assert row1["signature"] is not None

    h2 = VerifactuService.log_sif_event("SHUTDOWN_SYSTEM", "Parada del sistema de pruebas")
    assert h2 is not None
    assert h2 != h1

    with _get_connection() as conn:
        row2 = conn.execute("SELECT * FROM sif_event_log WHERE current_hash = ?", (h2,)).fetchone()
        assert row2 is not None
        assert row2["event_type"] == "SHUTDOWN_SYSTEM"
        assert row2["current_hash"] == h2
        assert row2["prev_event_hash"] == h1

def test_parse_aeat_soap_response_403_handling():
    """Verifica que el código de estado HTTP 403 se mapea a ERROR_AUTH con mensaje descriptivo."""
    raw_html_403 = "<html><head><title>403 Forbidden</title></head><body><h1>403 Forbidden</h1></body></html>"
    res = VerifactuService.parse_aeat_soap_response(raw_html_403, 403)
    
    assert res["status"] == "rejected"
    assert res["delivery_status"] == "ERROR_AUTH"
    assert "403 Forbidden" in res["message"]
    assert "prewww10.aeat.es" in res["message"]

def test_send_to_aeat_sif_dynamic_endpoint_resolution_for_test_cert():
    """Verifica que si se detecta un certificado o NIF de pruebas, se selecciona prewww10.aeat.es."""
    with patch.dict(os.environ, {"ALFONSO_AEAT_CERT": "data/certificados_prueba/certificado_pruebas.pem", "ALFONSO_AEAT_KEY": "data/certificados_prueba/clave_pruebas.pem"}, clear=False):
        # Desactivar temporalmente cualquier URL explícita para probar la resolución dinámica
        if "ALFONSO_AEAT_URL" in os.environ:
            del os.environ["ALFONSO_AEAT_URL"]
        
        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, text="<xml></xml>")
            VerifactuService.send_to_aeat_sif("<xml>test</xml>")
            
            assert mock_post.called
            url_called = mock_post.call_args[0][0]
            assert "prewww10.aeat.es" in url_called

def test_missing_issuer_identity_aborts_emission():
    """Verifica que si no hay identidad fiscal, se lanza IssuerIdentityError, no hay XML ni petición de red."""
    from app.domain.services.verifactu_service import IssuerIdentityError, VerifactuService
    from app.adapters.memory.memory import _get_connection

    # 1. Aseguramos que la tabla user_profile está vacía o sin razon_social
    with _get_connection() as conn:
        conn.execute("DELETE FROM user_profile")
        conn.commit()

    invoice_data = {
        "invoice_number": "FAC-ERR-001",
        "date_of_issue": "2026-09-23",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }

    # 2. Verificamos que se lanza IssuerIdentityError
    with pytest.raises(IssuerIdentityError) as exc_info:
        # Patch send_to_aeat_sif to ensure it's not called
        with patch.object(VerifactuService, "send_to_aeat_sif") as mock_send:
            VerifactuService.register_invoice(invoice_data)
            
    assert "no encontrada" in str(exc_info.value) or "Fallo al recuperar" in str(exc_info.value)
    
    # 3. Aseguramos que no se intentó llamar a red
    assert mock_send.call_count == 0
    
    # 4. Aseguramos que el estado de la factura no se ha modificado en la BD
    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM verifactu_invoices WHERE invoice_number = 'FAC-ERR-001'").fetchone()[0]
        assert count == 0

        assert count == 0

def test_sif_audit_write_error_prevents_silent_failure():
    """Verifica que si falla la escritura del log SIF al detectar tampering, no se silencia el error (EXC-02)."""
    from app.domain.services.verifactu_service import SIFAuditWriteError, VerifactuService
    from app.adapters.memory.memory import _get_connection

    # Preparamos una factura para registrarla normalmente
    invoice_data = {
        "invoice_number": "FAC-ERR-002",
        "date_of_issue": "2026-09-23",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 100.0,
        "iva_amount": 21.0,
        "total_amount": 121.0
    }
    
    # Aseguramos que haya un perfil válido para no disparar EXC-01
    with _get_connection() as conn:
        from app.utils.encryption import encryptor
        conn.execute("DELETE FROM user_profile")
        enc_name = encryptor.encrypt("Alfonso SIF User")
        conn.execute("INSERT INTO user_profile (razon_social, user_type, nif) VALUES (?, ?, ?)", (enc_name, 'COMPANY', '12345678Z'))
        conn.commit()

    VerifactuService.register_invoice(invoice_data)

    # Corrompemos la factura para que verifactu detecte el tampering
    with _get_connection() as conn:
        conn.execute("DROP TRIGGER IF EXISTS trg_prevent_update_verifactu")
        conn.execute("UPDATE verifactu_invoices SET total_amount = 999.0 WHERE invoice_number = 'FAC-ERR-002'")
        conn.commit()

    # Parcheamos log_sif_event para simular que falla la base de datos (e.g. timeout, disco lleno)
    with patch.object(VerifactuService, "log_sif_event", side_effect=Exception("DB Error Fake")):
        with pytest.raises(SIFAuditWriteError) as exc_info:
            VerifactuService.verify_chain_integrity()
    
    assert "Fallo crítico al registrar evento de auditoría SIF" in str(exc_info.value)
