"""
Test Unitario para ApprovalService (User Story 2: Human-in-the-Loop Approval Protocol).
Valida suspensión de operaciones, resolución (aprobar/rechazar) y manejo de timeouts.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from app.domain.services.approval_service import ApprovalService


@pytest.mark.asyncio
async def test_approval_service_lifecycle_approve():
    """Valida que una solicitud de aprobación quede pendiente y se resuelva como True al aprobar."""
    service = ApprovalService()
    
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_bridge:
        mock_bridge.return_value = {"status": "ok"}
        
        # Iniciar solicitud en background
        task = asyncio.create_task(
            service.request_approval(
                action_type="emit_invoice",
                details={"invoice_id": "F2026-0001", "total_amount": 1210.0},
                timeout=2.0
            )
        )
        
        # Ceder control para que se registre la solicitud
        await asyncio.sleep(0.01)
        
        assert len(service._pending_approvals) == 1
        action_id = list(service._pending_approvals.keys())[0]
        
        # Resolver positivamente
        res_ok = service.resolve_approval(action_id, approved=True)
        assert res_ok is True
        
        result = await task
        assert result is True
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_lifecycle_reject():
    """Valida que una solicitud de aprobación se resuelva como False al rechazar."""
    service = ApprovalService()
    
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_bridge:
        mock_bridge.return_value = {"status": "ok"}
        
        task = asyncio.create_task(
            service.request_approval(
                action_type="cancel_invoice",
                details={"invoice_id": "F2026-0002"},
                timeout=2.0
            )
        )
        await asyncio.sleep(0.01)
        
        action_id = list(service._pending_approvals.keys())[0]
        res_ok = service.resolve_approval(action_id, approved=False)
        assert res_ok is True
        
        result = await task
        assert result is False
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_timeout():
    """Valida que si no se resuelve dentro del tiempo límite, retorne False y limpie el estado."""
    service = ApprovalService()
    
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_bridge:
        mock_bridge.return_value = {"status": "ok"}
        
        # Timeout ultra-corto para el test
        result = await service.request_approval(
            action_type="submit_tax_model",
            details={"model": "303"},
            timeout=0.05
        )
        
        assert result is False
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_resolve_non_existent():
    """Valida que resolver un ID inexistente retorne False."""
    service = ApprovalService()
    res = service.resolve_approval("id-inexistente-123", approved=True)
    assert res is False
