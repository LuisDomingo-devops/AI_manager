import pytest
from app.domain.services.signature_service import SignatureService
from app.infrastructure.database.repositories.certificate_repository import CertificateRepository
from app.adapters.memory.memory import tenant_context

from app.adapters.memory.memory import _get_connection

@pytest.fixture
def cert_repo():
    return CertificateRepository(_get_connection())

@pytest.fixture
def signature_service(cert_repo):
    return SignatureService(cert_repo)

@pytest.fixture
def mock_p12_bytes():
    with open("tests/backend/fixtures/mock_cert.p12", "rb") as f:
        return f.read()

def test_store_software_certificate(signature_service, mock_p12_bytes):
    token = tenant_context.set("test-tenant")
    try:
        cert_id = signature_service.store_software_certificate("test-tenant", mock_p12_bytes, "password")
        assert cert_id is not None
        
        cert = signature_service.cert_repo.get_by_tenant("test-tenant")
        assert cert['cert_type'] == 'SOFTWARE'
        assert cert['subject_name'] is not None
        assert cert['encrypted_p12'] is not None
        assert cert['encrypted_password'] is not None
    finally:
        tenant_context.reset(token)

def test_sign_pdf_software(signature_service, mock_p12_bytes):
    token = tenant_context.set("test-tenant")
    try:
        signature_service.store_software_certificate("test-tenant", mock_p12_bytes, "password")
        
        # Create a dummy PDF bytes
        from reportlab.pdfgen import canvas
        from io import BytesIO
        
        buf = BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 100, "Hello World")
        c.save()
        pdf_bytes = buf.getvalue()
        
        signed_pdf = signature_service.sign_pdf("test-tenant", pdf_bytes, use_hardware=False)
        assert signed_pdf is not None
        assert len(signed_pdf) > len(pdf_bytes)
        assert b"adbe.pkcs7.detached" in signed_pdf
    finally:
        tenant_context.reset(token)
