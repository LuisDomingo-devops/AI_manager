import base64
from typing import Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from app.utils.encryption import encryptor
from app.infrastructure.database.connection_manager import _get_connection
from app.infrastructure.database.repositories.certificate_repository import CertificateRepository

def get_certificate_and_key(tenant_id: str = "default") -> Tuple[Optional[bytes], Optional[bytes]]:
    """
    Retrieves the certificate and private key from the database for the given tenant.
    Returns (cert_pem_bytes, private_key_pem_bytes)
    """
    with _get_connection(tenant_id) as conn:
        repo = CertificateRepository(conn)
        cert_data = repo.get_by_tenant(tenant_id)
        
        if not cert_data or not cert_data.get("encrypted_p12"):
            return None, None
            
        decrypted_p12 = encryptor.decrypt(cert_data["encrypted_p12"])
        
        # If it's a concatenated PEM string
        if "-----BEGIN PRIVATE KEY-----" in decrypted_p12 or "-----BEGIN RSA PRIVATE KEY-----" in decrypted_p12:
            return decrypted_p12.encode("utf-8"), decrypted_p12.encode("utf-8")
        else:
            # Handle P12/PFX loading if needed
            # This requires password and pkcs12 parsing
            # For our test certs, we loaded them as combined PEMs in load_certs.py
            return None, None

def sign_xml_dsig(xml_element, private_key_pem: bytes, cert_pem: bytes) -> str:
    """
    Signs an XML element using XMLDSig enveloped signature with RSA-SHA256.
    """
    from lxml import etree
    import signxml
    from signxml import XMLSigner

    signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha256")
    signed_root = signer.sign(xml_element, key=private_key_pem, cert=cert_pem)
    return etree.tostring(signed_root, encoding="utf-8").decode("utf-8")
