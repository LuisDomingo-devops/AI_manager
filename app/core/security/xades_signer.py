import base64
from lxml import etree
from signxml import XMLSigner, XMLVerifier, methods
from cryptography.hazmat.primitives import serialization
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def sign_invoice_xades(xml_bytes: bytes, private_key_pem: bytes, cert_pem: bytes) -> bytes:
    """
    Firma un documento XML (típicamente una factura electrónica) utilizando
    XMLDSig / XAdES, según lo requerido por VeriFactu y AEAT.
    
    Se espera que las claves estén en formato PEM.
    """
    root = etree.fromstring(xml_bytes)
    
    # Cargar certificado para validarlo (opcional, signxml usará los bytes directamente)
    cert = x509.load_pem_x509_certificate(cert_pem, default_backend())
    
    from signxml import XMLSigner
    
    # Configuramos el XMLSigner
    # Para Factura Electrónica en España se usa habitualmente RSA-SHA256
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"
    )
    
    signed_root = signer.sign(root, key=private_key_pem, cert=cert_pem)
    
    # Devolver el XML firmado
    return etree.tostring(signed_root, encoding='utf-8', xml_declaration=True)
