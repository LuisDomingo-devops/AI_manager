"""
Tests de integración para los endpoints REST del router de conciliación bancaria (/api/v1/bank/...).
Verifica la conformidad OpenAPI 3.0 para:
1. POST /api/v1/bank/statements/import
2. GET /api/v1/bank/movements/unreconciled
3. GET /api/v1/bank/reconciliation/suggestions
4. POST /api/v1/bank/reconciliation/apply (incluyendo HTTP 409 ante conflictos de conciliación doble)
"""
import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.database.connection_manager import write_transaction, tenant_context
from app.infrastructure.database.legal_connection import legal_write_transaction
from tests.backend.unit.test_norma43_parser import _generate_norma43_content


@pytest.fixture(autouse=True)
def clean_db():
    tenant_context.set("default")
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM bank_statements")
    with legal_write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM legal_journal_lines")
        cursor.execute("DELETE FROM legal_journal_entries")
    yield
    tenant_context.set("default")
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        cursor.execute("DELETE FROM bank_statements")


def test_router_import_statement_and_list_unreconciled():
    tenant_context.set("default")
    client = TestClient(app)

    # 1. Importar extracto Norma 43
    movements = [
        ("260115", 121000, "2", ["COBRO F2026-0099", "CLIENTE INTEGRACION"]),
        ("260116", 30000, "1", ["PAGO SERVICIO HOSTING", "PROVEEDOR"]),
    ]
    raw = _generate_norma43_content(100000, "2", movements, 191000, "2")

    response = client.post(
        "/api/v1/bank/statements/import",
        files={"file": ("extracto.n43", raw, "text/plain")},
        data={"format": "NORMA43", "account_iban": "ES9101821234123456789012"}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["source_type"] == "NORMA43"
    assert len(data["entries"]) == 2


    # 2. Consultar movimientos no conciliados
    unrec_res = client.get("/api/v1/bank/movements/unreconciled")
    assert unrec_res.status_code == 200
    unrec_data = unrec_res.json()
    assert len(unrec_data) == 2


def test_router_get_suggestions_and_apply_reconciliation():
    tenant_context.set("default")
    client = TestClient(app)

    # Insertar movimiento bancario y factura
    with write_transaction("default") as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bank_movements (
                id, account_iban, operation_date, value_date, movement_date, amount, balance_after,
                concept, reconciliation_status, tenant_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                50,
                "ES9101821234123456789012",
                "2026-01-20",
                "2026-01-20",
                "2026-01-20",
                1210.00,
                5210.00,
                "COBRO FACTURA F2026-0050",
                "UNRECONCILED",
                "default"
            )
        )
        cursor.execute(
            """
            INSERT INTO invoices (
                id, invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                base_imponible, iva_rate, iva_amount, total_amount, status, quarter, year
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                60,
                "F2026-0050",
                "2026-01-19",
                "ALFONSO AUTONOMO",
                "12345678Z",
                "CLIENTE SUGGESTION",
                "B12345678",
                1000.00,
                21.0,
                210.00,
                1210.00,
                "ISSUED",
                1,
                2026
            )
        )

    # 1. Obtener sugerencias
    sugg_res = client.get("/api/v1/bank/reconciliation/suggestions?min_score=0.70")
    assert sugg_res.status_code == 200
    sugg_list = sugg_res.json()
    assert len(sugg_list) >= 1
    sug = next((s for s in sugg_list if s["entry_id"] == 50), None)
    assert sug is not None, f"No se encontró sugerencia para entry_id 50 en {sugg_list}"
    assert sug["invoice_id"] == 60
    assert sug["score"] >= 0.70

    # 2. Aplicar conciliación
    apply_payload = {
        "tenant_id": "default",
        "entry_id": 50,
        "invoice_id": 60,
        "fee_amount": 0.0,
        "debit_account": "572",
        "credit_account": "430"
    }
    apply_res = client.post("/api/v1/bank/reconciliation/apply", json=apply_payload)
    assert apply_res.status_code == 200, apply_res.text
    apply_data = apply_res.json()
    assert apply_data["status"] == "RECONCILED"
    assert apply_data["journal_entry_id"] is not None

    # 3. Reintento (debe arrojar HTTP 409 Conflicto)
    retry_res = client.post("/api/v1/bank/reconciliation/apply", json=apply_payload)
    assert retry_res.status_code == 409
