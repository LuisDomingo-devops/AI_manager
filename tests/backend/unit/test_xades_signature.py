import pytest
from lxml import etree
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes, serialization
from cryptography import x509
from cryptography.x509.oid import NameOID
import datetime
from app.core.security.xades_signer import sign_invoice_xades

def generate_test_cert_and_key():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Madrid"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, u"Madrid"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Test Corp"),
        x509.NameAttribute(NameOID.COMMON_NAME, u"Test Cert"),
    ])
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        datetime.datetime.utcnow() + datetime.timedelta(days=10)
    ).sign(private_key, hashes.SHA256())
    
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    )
    return cert_pem, key_pem

def test_sign_invoice_xades():
    cert_pem, key_pem = generate_test_cert_and_key()
    
    xml_data = b'''<?xml version="1.0" encoding="UTF-8"?>
<Factura>
    <Detalle>Prueba de firma VeriFactu</Detalle>
    <Total>100.00</Total>
</Factura>
'''
    
    signed_xml = sign_invoice_xades(xml_data, key_pem, cert_pem)
    
    # Verificar que el XML resultante es válido y tiene el bloque de firma
    root = etree.fromstring(signed_xml)
    
    # La firma debe estar incrustada (Enveloped)
    namespaces = {'ds': 'http://www.w3.org/2000/09/xmldsig#'}
    signature_nodes = root.xpath('//ds:Signature', namespaces=namespaces)
    
    assert len(signature_nodes) == 1, "El XML firmado debe contener exactamente un nodo <Signature>"
    
    # Por ahora sólo validamos que signxml ha funcionado y añadido la firma XMLDSig
