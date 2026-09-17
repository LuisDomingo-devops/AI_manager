from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12, BestAvailableEncryption
import datetime
import os

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, u"ES"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Madrid"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, u"Madrid"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Alfonso Test"),
    x509.NameAttribute(NameOID.COMMON_NAME, u"Alfonso Test Cert"),
])

cert = x509.CertificateBuilder().subject_name(
    subject
).issuer_name(
    issuer
).public_key(
    key.public_key()
).serial_number(
    x509.random_serial_number()
).not_valid_before(
    datetime.datetime.now(datetime.timezone.utc)
).not_valid_after(
    datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=10)
).sign(key, hashes.SHA256())

p12 = pkcs12.serialize_key_and_certificates(
    b"test_cert", key, cert, None, BestAvailableEncryption(b"password")
)

os.makedirs("tests/backend/fixtures", exist_ok=True)
with open("tests/backend/fixtures/mock_cert.p12", "wb") as f:
    f.write(p12)

print("Mock cert generated at tests/backend/fixtures/mock_cert.p12")
