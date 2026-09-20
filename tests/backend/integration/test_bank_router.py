import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_mock_auth_xss_protection():
    payload = "<script>alert('xss')</script>"
    response = client.get(f"/bank/mock-auth?redirect={payload}")
    assert response.status_code == 200
    assert "<script>" not in response.text
    assert "&lt;script&gt;" in response.text
    
def test_callback_xss_protection():
    payload = "<img src=x onerror=alert(1)>"
    response = client.get(f"/callback?error=bad_request&details={payload}")
    assert response.status_code == 200
    assert "<img" not in response.text
    assert "&lt;img" in response.text
