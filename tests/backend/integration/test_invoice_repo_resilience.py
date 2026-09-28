import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository

def test_invoice_repository_decryption_resilience_and_logging():
    """
    Verifica que InvoiceRepository maneje adecuadamente registros corruptos sin romper
    la iteración de las demás facturas y registrando contexto específico en lugar del catch-all.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    
    # 2 filas: una corrupta y una válida
    mock_cursor.fetchall.return_value = [
        {
            "id": 1,
            "invoice_id": "CORRUPTED_CIPHERTEXT",
            "date": "enc_date",
            "issuer_name": "enc_issuer",
            "issuer_nif": "enc_nif",
            "receiver_name": "enc_recv",
            "receiver_nif": "enc_rnif",
            "base_imponible": "100.0",
            "iva_rate": "21.0",
            "iva_amount": "21.0",
            "irpf_rate": "0.0",
            "irpf_amount": "0.0",
            "total_amount": "121.0",
            "status": "emitida",
            "concept": "enc_concept",
            "file_path": "enc_path"
        },
        {
            "id": 2,
            "invoice_id": "VALID_CIPHERTEXT",
            "date": "enc_date",
            "issuer_name": "enc_issuer",
            "issuer_nif": "enc_nif",
            "receiver_name": "enc_recv",
            "receiver_nif": "enc_rnif",
            "base_imponible": "200.0",
            "iva_rate": "21.0",
            "iva_amount": "42.0",
            "irpf_rate": "0.0",
            "irpf_amount": "0.0",
            "total_amount": "242.0",
            "status": "emitida",
            "concept": "enc_concept",
            "file_path": "enc_path"
        }
    ]
    
    def side_effect_decrypt(val):
        if val == "CORRUPTED_CIPHERTEXT":
            raise ValueError("Corrupted ciphertext")
        if val == "VALID_CIPHERTEXT":
            return "FAC-2026-002"
        if val in ("100.0", "200.0", "21.0", "42.0", "0.0", "121.0", "242.0"):
            return val
        return "decrypted_text"

    with patch("app.infrastructure.database.repositories.invoice_repository._get_connection", return_value=mock_conn), \
         patch("app.infrastructure.database.repositories.invoice_repository.encryptor.decrypt", side_effect=side_effect_decrypt), \
         patch("app.infrastructure.database.repositories.invoice_repository.error_logger") as mock_logger:
        
        invoice = InvoiceRepository.find_invoice_by_id("FAC-2026-002")
        assert invoice is not None
        assert invoice["invoice_id"] == "FAC-2026-002"
        # Debe haber registrado un error por la fila corrupta
        assert mock_logger.error.called or mock_logger.warning.called
