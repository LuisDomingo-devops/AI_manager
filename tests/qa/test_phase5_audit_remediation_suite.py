import pytest
from datetime import datetime
from starlette.testclient import TestClient

from app.domain.services.tax_engine import TaxEngine
from app.domain.services.tax_parser_service import TaxParserService
from app.domain.services.task_manager import TaskManager
from app.domain.services.bank_service import BankService
from app.domain.services.verifactu_service import VerifactuService
from app.tools.server.billing_tools import (
    create_client,
    get_clients,
    delete_client,
    create_product,
    get_products,
    delete_product
)
from app.adapters.memory.memory import _get_connection, tenant_context, _init_db_schema
from app.main import app

@pytest.fixture(autouse=True)
def setup_audit_env():
    token = tenant_context.set("audit_remediation_tenant")
    with _get_connection() as conn:
        _init_db_schema(conn)
        conn.execute("DELETE FROM clients")
        conn.execute("DELETE FROM products")
        conn.execute("DELETE FROM tasks")
        conn.execute("DELETE FROM bank_connections")
        conn.commit()
    yield
    tenant_context.reset(token)


def test_tax_engine_no_default_vat_and_confidence():
    """
    Verifica que el motor fiscal no invente un IVA al 21% si no está en el texto
    y calcule la puntuación de confianza y la alerta de confirmación manual.
    """
    # 1. Texto sin porcentaje de IVA explícito
    text_without_vat = "Factura de compra de material de oficina por importe de 100 EUR."
    rates_info = TaxEngine.resolve_rates_with_confidence(text_without_vat)
    assert rates_info["is_iva_inferred"] is True
    assert rates_info["requires_manual_confirmation"] is True
    assert rates_info["confidence_score"] <= 0.70

    # 2. Texto con IVA explícito
    text_with_vat = "Factura de servicios profesionales Base 1000 EUR, IVA 21%, Total 1210 EUR."
    rates_info_explicit = TaxEngine.resolve_rates_with_confidence(text_with_vat)
    assert rates_info_explicit["is_iva_inferred"] is False
    assert rates_info_explicit["requires_manual_confirmation"] is False
    assert rates_info_explicit["iva_rate"] == 21.0
    assert rates_info_explicit["confidence_score"] == 1.0

    # 3. Texto con exención legal (Art. 20)
    text_exempt = "Honorarios médicos. Operación exenta de IVA según Art. 20 Ley 37/1992. Total 150 EUR."
    rates_info_exempt = TaxEngine.resolve_rates_with_confidence(text_exempt)
    assert rates_info_exempt["iva_rate"] == 0.0
    assert rates_info_exempt["is_iva_inferred"] is False


@pytest.mark.asyncio
async def test_soft_delete_clients_and_products():
    """
    Verifica el borrado lógico (Soft Delete) en clientes y productos para preservar la integridad histórica.
    """
    # 1. Crear cliente y producto
    r_cli = await create_client("Empresa Auditoria S.L.", "B12345674", "info@auditoria.es")
    assert r_cli["status"] == "ok"

    r_prod = await create_product("SKU-AUDIT-01", "Servicio Auditoría", 500.0)
    assert r_prod["status"] == "ok"

    # Obtener ID del cliente
    clients_res = await get_clients()
    assert len(clients_res["clients"]) == 1
    cli_id = clients_res["clients"][0]["id"]

    # 2. Ejecutar Soft Delete
    del_cli = await delete_client(cli_id, confirmed_by_user=True)
    assert del_cli["status"] == "ok"
    assert "desactivado" in del_cli["message"].lower()

    del_prod = await delete_product("SKU-AUDIT-01", confirmed_by_user=True)
    assert del_prod["status"] == "ok"

    # 3. Comprobar que ya no aparecen en el catálogo activo
    active_clients = await get_clients(include_deleted=False)
    assert len(active_clients["clients"]) == 0

    active_prods = await get_products(include_deleted=False)
    assert len(active_prods["products"]) == 0

    # 4. Comprobar que siguen existiendo físicamente en BD (Soft Delete)
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, is_active, deleted_at FROM clients WHERE id = ?", (cli_id,))
        row_c = cursor.fetchone()
        assert row_c is not None
        assert row_c["is_active"] == 0
        assert row_c["deleted_at"] is not None

        cursor.execute("SELECT sku, is_active, deleted_at FROM products WHERE sku = 'SKU-AUDIT-01'")
        row_p = cursor.fetchone()
        assert row_p is not None
        assert row_p["is_active"] == 0
        assert row_p["deleted_at"] is not None


def test_task_manager_lifecycle():
    """
    Verifica el ciclo de vida completo de la entidad Task para procesos en background.
    """
    # 1. Crear tarea
    task = TaskManager.create_task(
        task_type="audit_reconciliation",
        goal="Conciliar extractos bancarios del ejercicio 2026",
        payload={"year": 2026}
    )
    task_id = task["task_id"]
    assert task["status"] == "pending"

    # 2. Actualizar progreso
    ok_prog = TaskManager.update_task_progress(task_id, progress=0.5, status="running")
    assert ok_prog is True

    t_running = TaskManager.get_task(task_id)
    assert t_running["status"] == "running"
    assert t_running["progress"] == 0.5

    # 3. Completar tarea
    ok_comp = TaskManager.complete_task(task_id, result={"total_movements_matched": 42})
    assert ok_comp is True

    t_done = TaskManager.get_task(task_id)
    assert t_done["status"] == "completed"
    assert t_done["progress"] == 1.0
    assert t_done["result"]["total_movements_matched"] == 42


def test_open_banking_consent_expiry():
    """
    Verifica que el consentimiento PSD2 registre su expiración a 180 días y permita monitorizar su vigencia.
    """
    conn_id = BankService.add_connection(
        alias="Banco Santander Empresa",
        provider="gocardless",
        bank_name="Banco Santander",
        iban="ES9121000418450200051332"
    )
    assert conn_id > 0

    consent_info = BankService.check_consent_status(conn_id)
    assert consent_info["consent_status"] == "valid"
    assert consent_info["days_left"] >= 170
    assert consent_info["requires_renewal"] is False


def test_compliance_declaration_dynamic_expediente():
    """
    Verifica que la Declaración Responsable genere dinámicamente el expediente técnico de evidencias y firma RSA.
    """
    declaration = VerifactuService.get_compliance_declaration_dossier()
    assert declaration["status"] == "ok"
    assert "software_fingerprint_sha256" in declaration
    assert len(declaration["normativa_aplicable"]) >= 4
    assert "expediente_evidencias_tecnicas" in declaration
    assert "CONFORME" in declaration["expediente_evidencias_tecnicas"]["encadenamiento_criptografico_sha256"]
    assert declaration["digital_signature"] is not None


def test_api_v1_modular_endpoints():
    """
    Verifica que los routers modulares montados en /api/v1/ respondan correctamente.
    """
    client = TestClient(app)

    # 1. Compliance endpoint público
    res_comp = client.get("/api/v1/compliance/declaration")
    assert res_comp.status_code == 200
    assert res_comp.json()["status"] == "ok"

    # 2. Tasks endpoint con API key
    from app.config import settings
    headers = {"X-API-Key": settings.ALFONSO_API_KEY}
    res_tasks = client.get("/api/v1/tasks/", headers=headers)
    assert res_tasks.status_code == 200
    assert "tasks" in res_tasks.json()
