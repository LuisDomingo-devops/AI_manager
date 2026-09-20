import os
import base64
from typing import Optional, Dict, Any
from app.infrastructure.database.repositories.certificate_repository import CertificateRepository
from app.utils.encryption import encryptor
from cryptography.hazmat.primitives.serialization import pkcs12
import logging

logger = logging.getLogger(__name__)

class SignatureService:
    def __init__(self, cert_repo: CertificateRepository):
        self.cert_repo = cert_repo

    def _encrypt_bytes(self, data: bytes) -> str:
        b64_str = base64.b64encode(data).decode('utf-8')
        return encryptor.encrypt(b64_str)

    def _decrypt_bytes(self, encrypted_str: str) -> bytes:
        b64_str = encryptor.decrypt(encrypted_str)
        return base64.b64decode(b64_str)

    def store_software_certificate(self, tenant_id: str, p12_bytes: bytes, password: str) -> str:
        """
        Guarda el certificado .p12 o .pfx en la BD, verificando que la contrasena es correcta.
        """
        try:
            # Verify the certificate can be parsed with the password
            private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                p12_bytes, password.encode('utf-8')
            )
            
            subject = certificate.subject.rfc4514_string()
            valid_from = certificate.not_valid_before_utc.isoformat()
            valid_to = certificate.not_valid_after_utc.isoformat()
            
            encrypted_p12 = self._encrypt_bytes(p12_bytes)
            encrypted_password = encryptor.encrypt(password)
            
            cert_id = self.cert_repo.save(
                tenant_id=tenant_id,
                cert_type='SOFTWARE',
                encrypted_p12=encrypted_p12.encode('utf-8'), # The table defines it as BLOB, we can store utf-8 bytes
                encrypted_password=encrypted_password,
                subject_name=subject,
                valid_from=valid_from,
                valid_to=valid_to
            )
            return cert_id
        except Exception as e:
            logger.error(f"Error parsing or storing .p12 certificate: {e}")
            raise ValueError(f"Certificado no válido o contraseña incorrecta: {e}")



    def _sign_pdf_software(self, tenant_id: str, pdf_bytes: bytes) -> bytes:
        """
        Firma un PDF con el certificado p12 guardado.
        """
        cert_data = self.cert_repo.get_by_tenant(tenant_id)
        if not cert_data or cert_data['cert_type'] != 'SOFTWARE':
            raise ValueError("No hay un certificado software configurado para este tenant.")
        
        p12_bytes = self._decrypt_bytes(cert_data['encrypted_p12'].decode('utf-8'))
        password = encryptor.decrypt(cert_data['encrypted_password'])
        
        from pyhanko.sign.signers import SimpleSigner
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import signers
        from io import BytesIO
        
        import tempfile
        import os
        from pyhanko.sign.signers import SimpleSigner
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(p12_bytes)
            tmp_path = f.name
            
        try:
            signer = SimpleSigner.load_pkcs12(tmp_path, passphrase=password.encode('utf-8'))
            if signer is None:
                raise ValueError("Could not load signer from PKCS12 file")
        finally:
            os.remove(tmp_path)


        in_stream = BytesIO(pdf_bytes)
        out_stream = BytesIO()
        writer = IncrementalPdfFileWriter(in_stream)
        
        signers.sign_pdf(
            writer, signers.PdfSignatureMetadata(field_name='Signature1'),
            signer=signer, existing_fields_only=False
        )
        writer.write(out_stream)
        
        return out_stream.getvalue()



    def sign_pdf(self, tenant_id: str, pdf_bytes: bytes) -> bytes:
        return self._sign_pdf_software(tenant_id, pdf_bytes)
