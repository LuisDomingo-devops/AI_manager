"""
Tests de Integración de API de Facturación: GET /api/v1/billing/invoices (Spec 005 - US1).

Verifica que el endpoint de listado de facturas y el método InvoiceRepository.find_all_invoices()
operan de forma consistente, descifrando campos y permitiendo filtro por año.
Contrato de Discovery - Sección 7: BILLING.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection, tenant_context

client = TestClient(app)

@pytest.fixture(autouse=True)
def ensure_default_tenant_and_db():
    token = tenant_context.set("default")
    with _get_connection() as conn:
        conn.execute("DELETE FROM invoice_items")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM invoice_items")
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM fiscal_year_status")
        conn.commit()
    tenant_context.reset(token)


def test_list_invoices_endpoint_returns_decrypted_invoices():
    """
    Verifica que GET /api/v1/billing/invoices retorna 200 OK y la lista de facturas
    correctamente descifradas desde InvoiceRepository.
    """
    # 1. Insertar factura de prueba
    invoice_data = {
        "invoice_id": "F-2026-001",
        "date": "15/05/2026",
        "issuer_name": "Luis Domingo Emisor",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente API Facturas S.L.",
        "receiver_nif": "B12345678",
        "base_imponible": 500.0,
        "iva_rate": 21.0,
        "iva_amount": 105.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 605.0,
        "category": "income",
        "quarter": 2,
        "year": 2026,
        "concept": "Servicios de desarrollo SaaS",
        "status": "firmada"
    }
    InvoiceRepository.save(invoice_data)

    # 2. Llamar al endpoint
    response = client.get("/api/v1/billing/invoices", headers={"X-Client-ID": "default"})
    assert response.status_code == 200, f"Error en endpoint: {response.text}"
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["total"] == 1
    assert len(data["invoices"]) == 1

    inv = data["invoices"][0]
    assert inv["invoice_id"] == "F-2026-001"
    assert inv["issuer_nif"] == "12345678Z"
    assert inv["receiver_name"] == "Cliente API Facturas S.L."
    assert inv["total_amount"] == 605.0
    assert inv["year"] == 2026


def test_list_invoices_endpoint_filters_by_year():
    """
    Verifica que GET /api/v1/billing/invoices?year=2026 filtra adecuadamente por ejercicio fiscal.
    """
    # Guardar factura de 2026
    inv_2026 = {
        "invoice_id": "F-2026-002",
        "date": "20/06/2026",
        "issuer_name": "Luis Domingo",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente 2026",
        "receiver_nif": "B22222222",
        "base_imponible": 100.0,
        "iva_rate": 21.0,
        "iva_amount": 21.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 121.0,
        "category": "income",
        "quarter": 2,
        "year": 2026,
        "concept": "Factura 2026",
        "status": "firmada"
    }
    InvoiceRepository.save(inv_2026)

    # Filtrar por año 2026
    res_2026 = client.get("/api/v1/billing/invoices?year=2026", headers={"X-Client-ID": "default"})
    assert res_2026.status_code == 200
    assert res_2026.json()["total"] == 1

    # Filtrar por año 2025 (debe devolver 0)
    res_2025 = client.get("/api/v1/billing/invoices?year=2025", headers={"X-Client-ID": "default"})
    assert res_2025.status_code == 200
    assert res_2025.json()["total"] == 0
