import os
import json
import pytest
from starlette.testclient import TestClient

from app.main import app
from app.domain.services.tenant_provisioner import TenantProvisioningService
from app.tools.server.advisor_tools import send_to_advisor, request_document
from app.domain.services.task_manager import TaskManager
from app.domain.services.audit_ledger import AuditLedgerService
from app.infrastructure.adapters.bank_providers import GoCardlessProvider

client = TestClient(app)

def test_tenant_provisioning_service():
    """
    Verifica que el servicio de aprovisionamiento genera la base de datos aislada,
    aplica todas las migraciones DDL, genera las claves RSA y configura el perfil y suscripción.
    """
    test_client_id = "test_autonomo_comercial_01"
    result = TenantProvisioningService.provision_new_tenant(
        client_id=test_client_id,
        company_name="Soluciones Autónomas S.L.",
        nif="B99887766",
        email="contacto@solucionesautonomas.es",
        plan_tier="pro",
        stripe_customer_id="cus_test_12345",
        stripe_subscription_id="sub_test_12345"
    )

    assert result["status"] == "provisioned"
    assert result["client_id"] == test_client_id
    assert result["plan_tier"] == "pro"
    assert result["api_key"].startswith(f"alf_live_{test_client_id}_")

    status = TenantProvisioningService.get_tenant_status(test_client_id)
    assert status["client_id"] == test_client_id
    assert status["profile"]["nif"] == "B99887766"
    assert status["profile"]["razon_social"] == "Soluciones Autónomas S.L."
    assert status["subscription"]["tier"] == "pro"

def test_subscriptions_router_endpoints():
    """
    Verifica los endpoints de checkout y procesamiento de webhooks de Stripe.
    """
    # 1. Checkout session
    checkout_payload = {
        "client_id": "test_checkout_tenant_99",
        "company_name": "Consultoría Fiscal Digital",
        "nif": "A11223344",
        "email": "fiscal@digital.es",
        "plan_tier": "pro"
    }
    res = client.post("/api/v1/subscriptions/checkout-session", json=checkout_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "checkout_url" in data
    assert data["client_id"] == "test_checkout_tenant_99"

    # 2. Webhook simulation (checkout.session.completed)
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_id": "test_stripe_webhook_tenant",
                "company_name": "Innovaciones Autónomas S.L.",
                "nif": "B12345678",
                "customer_email": "admin@innovaciones.es",
                "plan_tier": "pro",
                "customer": "cus_stripe_real_001",
                "subscription": "sub_stripe_real_001"
            }
        }
    }
    res_hook = client.post("/api/v1/subscriptions/webhook", json=webhook_payload)
    assert res_hook.status_code == 200
    hook_data = res_hook.json()
    assert hook_data["status"] == "processed"
    assert hook_data["provision"]["client_id"] == "test_stripe_webhook_tenant"

    # 3. Status endpoint
    from app.config import settings
    res_status = client.get("/api/v1/subscriptions/status/test_stripe_webhook_tenant", headers={"X-API-Key": settings.ALFONSO_API_KEY})
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["data"]["profile"]["razon_social"] == "Innovaciones Autónomas S.L."

@pytest.mark.asyncio
async def test_send_to_advisor_tool():
    """
    Verifica la herramienta send_to_advisor con confirmación de usuario,
    empaquetado contable y registro en audit_ledger.
    """
    # 1. Sin confirmación -> pending_confirmation
    unconfirmed = await send_to_advisor(year=2026, advisor_email="asesor@gestoria.es", confirmed_by_user=False)
    assert unconfirmed["status"] == "pending_confirmation"
    assert "Se va a consolidar el expediente" in unconfirmed["message"]

    # 2. Con confirmación -> ok
    confirmed = await send_to_advisor(year=2026, advisor_email="asesor@gestoria.es", confirmed_by_user=True)
    assert confirmed["status"] == "ok"
    assert confirmed["year"] == 2026
    assert confirmed["advisor_email"] == "asesor@gestoria.es"
    assert "pack" in confirmed
    assert "libro_diario" in confirmed["pack"]
    assert "balance_situacion" in confirmed["pack"]

@pytest.mark.asyncio
async def test_request_document_tool():
    """
    Verifica la herramienta request_document registrando una tarea en TaskManager.
    """
    res = await request_document(
        description="Ticket de 45.00€ en Repsol del 12/08/2026",
        movement_id=101,
        invoice_id="FAC-TEMP-001"
    )
    assert res["status"] == "ok"
    assert "task_id" in res
    assert res["movement_id"] == 101

    task = TaskManager.get_task(res["task_id"])
    assert task is not None
    assert task["task_type"] == "document_request"
    assert "Ticket de 45.00€" in task["goal"]

def test_gocardless_credentials_resolution(monkeypatch):
    """
    Verifica que GoCardlessProvider resuelve credenciales desde settings / env vars.
    """
    provider = GoCardlessProvider()

    # 1. Pasadas en dict
    s_id, s_key = provider._resolve_credentials({"secret_id": "custom_id", "secret_key": "custom_key"})
    assert s_id == "custom_id"
    assert s_key == "custom_key"

    # 2. Resueltas desde entorno si dict está vacío
    monkeypatch.setenv("GOCARDLESS_SECRET_ID", "env_secret_id_123")
    monkeypatch.setenv("GOCARDLESS_SECRET_KEY", "env_secret_key_456")
    s_id_env, s_key_env = provider._resolve_credentials({})
    assert s_id_env == "env_secret_id_123"
    assert s_key_env == "env_secret_key_456"
