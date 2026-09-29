import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch
from starlette.testclient import TestClient

from app.main import app
from app.utils.paths import DATA_DIR
from app.domain.services.tenant_provisioner import TenantProvisioningService

client = TestClient(app)

def test_stripe_idempotency_qa_multi_event_persistence_and_recovery(monkeypatch, tmp_path):
    """
    Suite de QA para idempotencia y resiliencia de webhooks de Stripe:
    1. Envía ráfaga de 3 eventos diferentes (evt_qa_01, evt_qa_02, evt_qa_03) -> todos procesados.
    2. Envía reintentos intercalados (evt_qa_02 de nuevo) -> ignorado por ya procesado.
    3. Simula archivo corrupto/inválido en disco y comprueba auto-recuperación sin error 500.
    4. Garantiza que solo se ejecuta provision_new_tenant para eventos genuinamente nuevos.
    """
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_qa_secret")

    events_file = DATA_DIR / "stripe_events.json"
    backup_file = None
    # Salvaguardar archivo real si existe durante el test
    if events_file.exists():
        backup_file = DATA_DIR / "stripe_events.json.bak_test"
        events_file.replace(backup_file)

    try:
        mock_stripe = MagicMock()
        monkeypatch.setitem(sys.modules, "stripe", mock_stripe)

        processed_ids = set()

        with patch.object(
            TenantProvisioningService,
            "provision_new_tenant",
            side_effect=lambda **kwargs: {"status": "provisioned", "client_id": kwargs.get("client_id")}
        ) as mock_provision:
            # 1. Enviar eventos 1, 2 y 3
            for i in [1, 2, 3]:
                evt_id = f"evt_qa_idemp_seq_{i}"
                payload = {
                    "id": evt_id,
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "client_id": f"tenant_qa_{i}",
                            "company_name": f"QA Company {i}",
                            "nif": f"B1234567{i}",
                            "customer_email": f"qa_{i}@example.com"
                        }
                    }
                }
                mock_stripe.Webhook.construct_event.return_value = payload

                res = client.post(
                    "/api/v1/subscriptions/webhook",
                    json=payload,
                    headers={"stripe-signature": "t=1,v1=test"}
                )
                assert res.status_code == 200, f"Fallo al procesar {evt_id}: {res.text}"
                assert res.json()["status"] == "processed"
                processed_ids.add(evt_id)

            assert mock_provision.call_count == 3, "Deben haberse procesado exactamente 3 eventos nuevos"

            # 2. Reenviar evento 2 y evento 1 (duplicados)
            for i in [2, 1]:
                evt_id = f"evt_qa_idemp_seq_{i}"
                payload = {
                    "id": evt_id,
                    "type": "checkout.session.completed",
                    "data": {
                        "object": {
                            "client_id": f"tenant_qa_{i}",
                            "company_name": f"QA Company {i}",
                            "nif": f"B1234567{i}",
                            "customer_email": f"qa_{i}@example.com"
                        }
                    }
                }
                mock_stripe.Webhook.construct_event.return_value = payload

                res = client.post(
                    "/api/v1/subscriptions/webhook",
                    json=payload,
                    headers={"stripe-signature": "t=1,v1=test"}
                )
                assert res.status_code == 200
                res_data = res.json()
                assert res_data["status"] == "ignored", f"El reintento de {evt_id} debió ser ignorado"
                assert res_data.get("reason") == "already_processed"

            # El call count sigue siendo exactamente 3
            assert mock_provision.call_count == 3, "No deben invocarse llamadas adicionales al aprovisionador"

            # 3. Comprobar recuperación ante archivo corrupto
            with open(events_file, "w", encoding="utf-8") as f:
                f.write("{ invalid json corrupted content !#@$% ")

            evt_recovery = "evt_qa_recovery_999"
            payload_rec = {
                "id": evt_recovery,
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "client_id": "tenant_recovery",
                        "company_name": "Recovery S.L.",
                        "nif": "B99999999",
                        "customer_email": "rec@example.com"
                    }
                }
            }
            mock_stripe.Webhook.construct_event.return_value = payload_rec

            res_rec = client.post(
                "/api/v1/subscriptions/webhook",
                json=payload_rec,
                headers={"stripe-signature": "t=1,v1=test"}
            )
            assert res_rec.status_code == 200, "Debe recuperarse y procesar aún con archivo previo corrupto"
            assert res_rec.json()["status"] == "processed"
            assert mock_provision.call_count == 4

    finally:
        # Restaurar backup si existía
        if backup_file and backup_file.exists():
            if events_file.exists():
                events_file.unlink()
            backup_file.replace(events_file)
