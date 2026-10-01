"""
Test de Integración para Envío de Facturas por SMTP Corporativo (User Story 7).
Valida la generación del correo con PDF adjunto y la gestión de conexiones SMTP seguras.
"""

from unittest.mock import MagicMock, patch
import pytest
from app.infrastructure.external.smtp_service import SmtpService


def test_smtp_delivery_with_pdf_attachment():
    """Valida el ensamblado MIME de un correo de factura con PDF adjunto y llamada a smtplib."""
    service = SmtpService()
    
    config = {
        "smtp_server": "smtp.dominio-usuario.es",
        "smtp_port": 587,
        "username": "facturas@dominio-usuario.es",
        "password": "secret_password",
        "use_tls": True
    }
    
    dummy_pdf_bytes = b"%PDF-1.4 ... Factura Veri*Factu Oficial F2026-0001 ..."
    
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server
        
        result = service.send_invoice_email(
            config=config,
            recipient_email="cliente@acme.com",
            subject="Factura F2026-0001 de Alfonso Autónomo",
            body="Estimado cliente,\nAdjuntamos la factura emitida.\nSaludos.",
            pdf_bytes=dummy_pdf_bytes,
            pdf_filename="Factura_F2026_0001.pdf"
        )
        
        assert result["success"] is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("facturas@dominio-usuario.es", "secret_password")
        mock_server.send_message.assert_called_once()
        
        # Validar que el mensaje enviado contenga el adjunto
        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["To"] == "cliente@acme.com"
        assert "Factura_F2026_0001.pdf" in str(sent_msg)


def test_smtp_delivery_handles_connection_error():
    """Valida que ante fallo de conexión el servicio capture el error sin lanzar excepciones no controladas."""
    service = SmtpService()
    config = {
        "smtp_server": "smtp.servidor-invalido.xyz",
        "smtp_port": 587,
        "username": "user",
        "password": "pass",
        "use_tls": True
    }
    
    with patch("smtplib.SMTP", side_effect=OSError("Servidor SMTP no alcanzable")):
        result = service.send_invoice_email(
            config=config,
            recipient_email="cliente@acme.com",
            subject="Factura",
            body="Texto",
            pdf_bytes=b"dummy",
            pdf_filename="factura.pdf"
        )
        assert result["success"] is False
        assert "no alcanzable" in result.get("error", "").lower() or "error" in result.get("error", "").lower()
