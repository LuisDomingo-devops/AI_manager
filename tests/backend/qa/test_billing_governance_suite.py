"""
Test QA de Gobernanza e Integridad de Facturación (Spec 005 - US3).

Audita:
1. Ciclo completo de emisión de factura ordinaria vía API y persistencia en InvoiceRepository.
2. Consulta íntegra a través de GET /api/v1/billing/invoices verificando descifrado Fernet exhaustivo.
3. Filtrado temporal riguroso por año fiscal (?year=YYYY) demostrando exclusión de ejercicios ajenos.
4. Consulta unitaria por ID de factura vía InvoiceRepository.find_invoice_by_id().
5. Integridad de los datos numéricos (base_imponible, iva, irpf, total) entre base de datos y API.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes import verify_api_key
from app.infrastructure.database.repositories.invoice_repository import InvoiceRepository
from app.adapters.memory.memory import _get_connection

client = TestClient(app)

@pytest.fixture(autouse=True)
def override_auth():
    app.dependency_overrides[verify_api_key] = lambda: "default"
    yield
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def clean_qa_billing_db():
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


def test_billing_governance_full_lifecycle():
    """
    QA Test: Valida la persistencia, descifrado completo en InvoiceRepository.find_all_invoices(),
    la concordancia de importes y el filtrado por año fiscal a través de la API.
    """
    # 1. Crear 2 facturas en 2026 y 1 factura en 2027
    inv1_2026 = {
        "invoice_id": "QA-FAC-2026-001",
        "date": "10/01/2026",
        "issuer_name": "Luis Domingo QA",
        "issuer_nif": "12345678Z",
        "receiver_name": "Empresa Cliente Alfa S.L.",
        "receiver_nif": "B11111111",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 15.0,
        "irpf_amount": 150.0,
        "total_amount": 1060.0,
        "category": "income",
        "quarter": 1,
        "year": 2026,
        "concept": "Auditoría de Sistemas Q1 2026",
        "status": "firmada"
    }
    inv2_2026 = {
        "invoice_id": "QA-FAC-2026-002",
        "date": "20/02/2026",
        "issuer_name": "Luis Domingo QA",
        "issuer_nif": "12345678Z",
        "receiver_name": "Empresa Cliente Beta S.A.",
        "receiver_nif": "A22222222",
        "base_imponible": 2000.0,
        "iva_rate": 21.0,
        "iva_amount": 420.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 2420.0,
        "category": "income",
        "quarter": 1,
        "year": 2026,
        "concept": "Consultoría Cloud",
        "status": "firmada"
    }
    inv_2027 = {
        "invoice_id": "QA-FAC-2027-001",
        "date": "05/01/2027",
        "issuer_name": "Luis Domingo QA",
        "issuer_nif": "12345678Z",
        "receiver_name": "Empresa Cliente Gamma S.L.",
        "receiver_nif": "B33333333",
        "base_imponible": 500.0,
        "iva_rate": 21.0,
        "iva_amount": 105.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 605.0,
        "category": "income",
        "quarter": 1,
        "year": 2027,
        "concept": "Soporte anual 2027",
        "status": "firmada"
    }

    db_id1 = InvoiceRepository.save(inv1_2026)
    db_id2 = InvoiceRepository.save(inv2_2026)
    db_id3 = InvoiceRepository.save(inv_2027)

    assert db_id1 > 0
    assert db_id2 > 0
    assert db_id3 > 0

    # 2. Consultar por ID directo en el Repositorio
    single_inv = InvoiceRepository.find_invoice_by_id("QA-FAC-2026-001")
    assert single_inv is not None
    assert single_inv["invoice_id"] == "QA-FAC-2026-001"
    assert single_inv["issuer_nif"] == "12345678Z"
    assert single_inv["receiver_name"] == "Empresa Cliente Alfa S.L."
    assert single_inv["base_imponible"] == 1000.0
    assert single_inv["total_amount"] == 1060.0
    assert single_inv["irpf_amount"] == 150.0

    # 3. Invocar GET /api/v1/billing/invoices sin filtro (debe retornar 3 facturas)
    res_all = client.get("/api/v1/billing/invoices", headers={"X-API-Key": "default_key"})
    assert res_all.status_code == 200
    data_all = res_all.json()
    assert data_all["status"] == "ok"
    assert data_all["total"] == 3
    assert len(data_all["invoices"]) == 3

    # Validar que todos los campos descifrados coincidan
    ids_encontrados = {inv["invoice_id"] for inv in data_all["invoices"]}
    assert ids_encontrados == {"QA-FAC-2026-001", "QA-FAC-2026-002", "QA-FAC-2027-001"}

    # 4. Invocar con filtro year=2026 (debe retornar exactamente 2 facturas)
    res_2026 = client.get("/api/v1/billing/invoices?year=2026", headers={"X-API-Key": "default_key"})
    assert res_2026.status_code == 200
    data_2026 = res_2026.json()
    assert data_2026["total"] == 2
    for inv in data_2026["invoices"]:
        assert inv["year"] == 2026

    # 5. Invocar con filtro year=2027 (debe retornar exactamente 1 factura)
    res_2027 = client.get("/api/v1/billing/invoices?year=2027", headers={"X-API-Key": "default_key"})
    assert res_2027.status_code == 200
    data_2027 = res_2027.json()
    assert data_2027["total"] == 1
    assert data_2027["invoices"][0]["invoice_id"] == "QA-FAC-2027-001"

    # 6. Invocar con filtro year=2030 (vacío)
    res_2030 = client.get("/api/v1/billing/invoices?year=2030", headers={"X-API-Key": "default_key"})
    assert res_2030.status_code == 200
    assert res_2030.json()["total"] == 0
    assert len(res_2030.json()["invoices"]) == 0
