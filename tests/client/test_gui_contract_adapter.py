"""Prueba de QA de cliente PyQt6 sobre adaptador de contrato en memoria (T038/T041 - TDD).

Valida que el cliente de la aplicación de escritorio consuma los endpoints
locales mediante el adaptador de contrato tipado LocalApiClient con transporte
en memoria, eliminando la necesidad de levantar servidores HTTPServer sockets ad-hoc.
"""

from fastapi.testclient import TestClient
from app.main import app
from client.api_client import LocalApiClient


def test_local_api_client_in_memory_transport():
    test_session = TestClient(app)
    api_client = LocalApiClient(
        base_url="http://testserver",
        client_session=test_session,
    )

    result = api_client.issue_legal_invoice(
        client_name="Cliente E2E Desktop",
        client_nif="A12345678",
        amount=1000.0,
        concept="Servicios de ingeniería contable",
        iva_rate=21.0,
    )

    assert "invoice_number" in result
    assert result["invoice_number"].startswith("F2026-")
    assert result["total_amount"] == 1210.0
    assert "verifactu_hash" in result
    assert len(result["verifactu_hash"]) == 64


def test_local_api_client_get_invoices_in_memory():
    test_session = TestClient(app)
    api_client = LocalApiClient(client_session=test_session)

    invoices = api_client.get_invoices()
    assert "invoices" in invoices
    assert isinstance(invoices["invoices"], list)
