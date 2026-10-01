"""
Test de Integración para el Protocolo de Aprobación Humana (User Story 2).
Valida la interacción completa entre ApprovalService, WebSocket bridge y endpoints REST de resolución.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.domain.services.approval_service import approval_service


@pytest.fixture
def client():
    # Usamos TestClient con la clave de API requerida por las rutas
    return TestClient(app, headers={"X-API-Key": "test_key"})


@pytest.mark.asyncio
async def test_integration_approval_resolve_endpoint(client):
    """Valida la resolución de una solicitud de aprobación vía endpoint REST /approvals/{id}/resolve."""
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_bridge:
        mock_bridge.return_value = {"status": "ok"}
        
        # 1. Iniciar solicitud que suspende la ejecución
        task = asyncio.create_task(
            approval_service.request_approval(
                action_type="emit_invoice",
                details={
                    "recipient_name": "ACME S.L.",
                    "recipient_nif": "B12345674",
                    "total_amount": 1210.00
                },
                timeout=5.0
            )
        )
        
        # Esperar a que se registre en pending_approvals
        for _ in range(50):
            if len(approval_service._pending_approvals) > 0:
                break
            await asyncio.sleep(0.02)
            
        assert len(approval_service._pending_approvals) == 1
        action_id = list(approval_service._pending_approvals.keys())[0]
        
        # Verificar que alfonso_bridge recibió el comando approval_required con la estructura correcta
        mock_bridge.assert_called_once()
        call_args = mock_bridge.call_args
        assert call_args[0][0] == "approval_required"
        assert call_args[1]["params"]["action_id"] == action_id
        assert call_args[1]["params"]["action_type"] == "emit_invoice"
        assert call_args[1]["params"]["details"]["recipient_name"] == "ACME S.L."
        
        # 2. Simular resolución por parte de la GUI mediante POST /api/v1/approvals/{id}/resolve (o /approvals/{id}/resolve)
        response = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"approved": True, "user_notes": "Aprobado por el usuario"}
        )
        
        # Si la ruta canónica aún no está implementada, probar la ruta sin prefijo
        if response.status_code == 404:
            response = client.post(
                f"/approvals/{action_id}/resolve",
                json={"approved": True, "user_notes": "Aprobado por el usuario"}
            )
            
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "ok"
        
        # 3. La tarea suspendida se debe haber desbloqueado y retornado True
        result = await task
        assert result is True
        assert len(approval_service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_integration_approval_reject_endpoint(client):
    """Valida el rechazo de una solicitud vía endpoint REST."""
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_bridge:
        mock_bridge.return_value = {"status": "ok"}
        
        task = asyncio.create_task(
            approval_service.request_approval(
                action_type="purge_records",
                details={"reason": "test"},
                timeout=5.0
            )
        )
        
        for _ in range(50):
            if len(approval_service._pending_approvals) > 0:
                break
            await asyncio.sleep(0.02)
            
        action_id = list(approval_service._pending_approvals.keys())[0]
        
        response = client.post(
            f"/api/v1/approvals/{action_id}/resolve",
            json={"approved": False, "user_notes": "Rechazado por el usuario"}
        )
        if response.status_code == 404:
            response = client.post(
                f"/approvals/{action_id}/resolve",
                json={"approved": False, "user_notes": "Rechazado por el usuario"}
            )
            
        assert response.status_code == 200
        result = await task
        assert result is False
