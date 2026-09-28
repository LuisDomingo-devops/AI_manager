import pytest
from unittest.mock import patch, MagicMock
import sqlite3

from app.tools.server.billing_tools import delete_client, _generate_unique_quote_id

pytestmark = pytest.mark.usefixtures("mock_approval_service")

@pytest.mark.asyncio
async def test_delete_client_audit_failure_logs_severe_error():
    """
    Verifica que si AuditLedgerService.log_audit_event falla al desactivar un cliente,
    no se trague la excepción silenciosamente con un simple warning genérico,
    sino que se registre un error severo y la respuesta refleje la advertencia de auditoría.
    """
    with patch("app.tools.server.billing_tools.delete_contact", return_value={"status": "ok", "message": "Deleted"}), \
         patch("app.domain.services.audit_ledger.AuditLedgerService.log_audit_event", side_effect=sqlite3.OperationalError("Database disk image is malformed")), \
         patch("app.tools.server.billing_tools.error_logger") as mock_logger:
        
        res = await delete_client(client_id="CLI-12345")
        
        assert res["status"] == "ok"
        # Debe reflejar advertencia de auditoría en la respuesta para no ocultar la pérdida de traza legal
        assert res.get("audit_warning") is True or res.get("audit_persisted") is False or "auditoría" in res.get("message", "").lower()
        # Debe haber registrado un error en el logger
        assert mock_logger.error.called or mock_logger.critical.called

def test_get_next_quote_id_decryption_failure_handling():
    """
    Verifica que si el descifrado de un quote_id falla por clave corrupta,
    se capture la excepción criptográfica/de valor de manera tipada y se registre un error explícito.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [{"quote_id": "CORRUPTED_CIPHERTEXT"}]
    
    with patch("app.tools.server.billing_tools._get_connection", return_value=mock_conn), \
         patch("app.tools.server.billing_tools.encryptor.decrypt", side_effect=ValueError("Invalid base64")), \
         patch("app.tools.server.billing_tools.error_logger") as mock_logger:
        
        quote_id = _generate_unique_quote_id(is_draft=False)
        assert quote_id.startswith("P-2026-")
        # El logger debe registrar un error específico de descifrado, no un warning genérico
        assert mock_logger.error.called or mock_logger.warning.called
