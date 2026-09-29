import sys
import json
import uuid
import pytest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from app.main import app
from app.utils.paths import DATA_DIR
from app.domain.services.tenant_provisioner import TenantProvisioningService

client = TestClient(app)

def test_stripe_webhook_idempotency_rejects_duplicate_events(monkeypatch):
    """
    Verifica el contrato estricto de idempotencia de Stripe (Sección 9 del Discovery Contract):
    1. Recibe webhook A con un event_id específico.
    2. Procesa A exitosamente llamando a TenantProvisioningService.provision_new_tenant.
    3. Recibe webhook A de nuevo con el mismo event_id.
    4. Comprueba que NO duplica efectos: status='ignored', reason='already_processed'.
    5. TenantProvisioningService.provision_new_tenant NO se ejecuta una segunda vez.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_idempotency_secret")

    event_id = f"evt_test_idemp_{uuid.uuid4().hex}"
    webhook_event = {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_id": "tenant_idemp_01",
                "company_name": "Empresa Idempotente S.L.",
                "nif": "B12345678",
                "customer_email": "admin@empresa-idemp.es",
                "plan_tier": "pro",
                "customer": "cus_real_001",
                "subscription": "sub_real_001"
            }
        }
    }

    mock_stripe = MagicMock()
    mock_stripe.Webhook.construct_event.return_value = webhook_event
    monkeypatch.setitem(sys.modules, "stripe", mock_stripe)

    try:
        with patch.object(
            TenantProvisioningService,
            "provision_new_tenant",
            return_value={"status": "provisioned", "client_id": "tenant_idemp_01"}
        ) as mock_provision:
            # Primer envío de webhook A
            res1 = client.post(
                "/api/v1/subscriptions/webhook",
                json=webhook_event,
                headers={"stripe-signature": "t=1,v1=test_sig"}
            )
            assert res1.status_code == 200, f"El primer envío falló: {res1.text}"
            data1 = res1.json()
            assert data1["status"] == "processed", f"Estado esperado 'processed', recibido {data1}"
            assert mock_provision.call_count == 1, "Debe haberse invocado el aprovisionamiento 1 vez"

            # Segundo envío idéntico de webhook A
            res2 = client.post(
                "/api/v1/subscriptions/webhook",
                json=webhook_event,
                headers={"stripe-signature": "t=1,v1=test_sig"}
            )
            assert res2.status_code == 200, f"El segundo envío falló: {res2.text}"
            data2 = res2.json()
            assert data2["status"] == "ignored", (
                f"El evento duplicado debe ser ignorado para idempotencia, recibido: {data2}"
            )
            assert data2.get("reason") == "already_processed", (
                f"El motivo debe ser 'already_processed', recibido: {data2}"
            )
            assert mock_provision.call_count == 1, (
                "El aprovisionamiento NO debe llamarse por segunda vez en un evento duplicado"
            )
    finally:
        events_file = DATA_DIR / "stripe_events.json"
        if events_file.exists():
            try:
                with open(events_file, "r", encoding="utf-8") as f:
                    evts = json.load(f)
                if isinstance(evts, list) and event_id in evts:
                    evts.remove(event_id)
                    with open(events_file, "w", encoding="utf-8") as f:
                        json.dump(evts, f)
            except Exception:
                pass

