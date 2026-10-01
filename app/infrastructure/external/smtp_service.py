"""
Servicio de envío de correo SMTP corporativo para entrega de facturas y documentos oficiales.
Utiliza conexiones cifradas TLS/SSL y ensamblado multipart/mixed para adjuntos PDF.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from typing import Dict, Any, Optional
from app.utils.logger import app_logger


class SmtpService:
    """Envía correos electrónicos directamente a través del servidor SMTP configurado por el usuario."""

    def send_invoice_email(
        self,
        config: Dict[str, Any],
        recipient_email: str,
        subject: str,
        body: str,
        pdf_bytes: bytes,
        pdf_filename: str = "Factura.pdf"
    ) -> Dict[str, Any]:
        server_host = config.get("smtp_server", "localhost")
        server_port = int(config.get("smtp_port", 587))
        username = config.get("username", "")
        password = config.get("password", "")
        use_tls = config.get("use_tls", True)
        use_ssl = config.get("use_ssl", False)
        sender_email = config.get("sender_email") or username

        # Construcción del mensaje MIME
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject

        # Cuerpo del mensaje
        msg.attach(MIMEText(body, "plain", "utf-8"))

        # Adjunto PDF
        pdf_part = MIMEApplication(pdf_bytes, _subtype="pdf")
        pdf_part.add_header("Content-Disposition", f"attachment; filename=\"{pdf_filename}\"")
        msg.attach(pdf_part)

        try:
            if use_ssl:
                with smtplib.SMTP_SSL(server_host, server_port, timeout=15.0) as server:
                    if username and password:
                        server.login(username, password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(server_host, server_port, timeout=15.0) as server:
                    if use_tls:
                        server.starttls()
                    if username and password:
                        server.login(username, password)
                    server.send_message(msg)

            app_logger.info(f"Factura enviada por SMTP exitosamente a {recipient_email}")
            return {"success": True, "message": f"Correo enviado a {recipient_email}"}
        except Exception as e:
            err_msg = f"Error al enviar correo por SMTP: {str(e)}"
            app_logger.error(err_msg)
            return {"success": False, "error": err_msg}
