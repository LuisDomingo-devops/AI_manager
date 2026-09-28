"""
Tests Unitarios: Contratos de Invocación y Resolución de ApprovalService (Spec 002 - TDD)
Verifica que ApprovalService responda de forma determinista ante aprobaciones,
rechazos, expiraciones por timeout y que soporte llamadas tanto de instancia como de clase.
"""

import asyncio
import pytest
from unittest.mock import patch, AsyncMock
from app.domain.services.approval_service import ApprovalService, approval_service

@pytest.mark.asyncio
async def test_approval_service_instance_approved():
    """Valida el camino feliz de aprobación resuelta positivamente."""
    service = ApprovalService()
    
    with patch("app.infrastructure.adapters.alfonso_bridge.bridge.send_command", new_callable=AsyncMock) as mock_send:
        task = asyncio.create_task(service.request_approval("test_action", {"key": "val"}, timeout=1.0))
        
        # Ceder control brevemente para que se cree el pending approval
        await asyncio.sleep(0.01)
        assert len(service._pending_approvals) == 1
        action_id = list(service._pending_approvals.keys())[0]
        
        # Resolver como Aprobado
        resolved = service.resolve_approval(action_id, approved=True)
        assert resolved is True
        
        res = await task
        assert res is True
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_instance_rejected():
    """Valida el camino en que el usuario humano rechaza la operación."""
    service = ApprovalService()
    
    with patch("app.infrastructure.adapters.alfonso_bridge.bridge.send_command", new_callable=AsyncMock) as mock_send:
        task = asyncio.create_task(service.request_approval("test_action_reject", {"key": "val"}, timeout=1.0))
        
        await asyncio.sleep(0.01)
        action_id = list(service._pending_approvals.keys())[0]
        
        # Resolver como Rechazado
        resolved = service.resolve_approval(action_id, approved=False)
        assert resolved is True
        
        res = await task
        assert res is False
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_instance_timeout():
    """Valida que si expira el tiempo de espera, se retorna False y se limpia el mapa."""
    service = ApprovalService()
    
    with patch("app.infrastructure.adapters.alfonso_bridge.bridge.send_command", new_callable=AsyncMock) as mock_send:
        res = await service.request_approval("test_action_timeout", {"key": "val"}, timeout=0.05)
        assert res is False
        assert len(service._pending_approvals) == 0


@pytest.mark.asyncio
async def test_approval_service_classmethod_compatibility():
    """
    Verifica que ApprovalService.request_approval pueda ser invocado directamente desde la clase
    sin fallar por 'missing 1 required positional argument: self', garantizando interoperabilidad
    defensiva con herramientas antiguas.
    """
    with patch("app.infrastructure.adapters.alfonso_bridge.bridge.send_command", new_callable=AsyncMock):
        task = asyncio.create_task(ApprovalService.request_approval("class_action", {}, timeout=1.0))
        await asyncio.sleep(0.01)
        
        action_id = list(approval_service._pending_approvals.keys())[0]
        approval_service.resolve_approval(action_id, approved=True)
        
        res = await task
        assert res is True
