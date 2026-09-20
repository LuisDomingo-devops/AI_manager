import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from app.domain.services.approval_service import ApprovalService

@pytest.fixture
def approval_service():
    from app.domain.services.approval_service import ApprovalService as RealApprovalService
    import importlib
    import app.domain.services.approval_service
    importlib.reload(app.domain.services.approval_service)
    
    with patch("app.domain.services.approval_service.ApprovalService.request_approval", new=RealApprovalService.request_approval):
        yield RealApprovalService()

@pytest.mark.asyncio
async def test_approval_flow_approved(approval_service):
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_send:
        
        async def resolve_later():
            await asyncio.sleep(0.1)
            # Find the action_id that was generated
            action_id = list(approval_service._pending_approvals.keys())[0]
            approval_service.resolve_approval(action_id, True)
            
        task = asyncio.create_task(resolve_later())
        
        result = await approval_service.request_approval(
            action_type="test_action",
            details={"foo": "bar"},
            timeout=1.0
        )
        
        await task
        
        assert result is True
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        assert args[0] == "approval_required"
        assert kwargs["params"]["action_type"] == "test_action"

@pytest.mark.asyncio
async def test_approval_flow_rejected(approval_service):
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock) as mock_send:
        
        async def resolve_later():
            await asyncio.sleep(0.1)
            action_id = list(approval_service._pending_approvals.keys())[0]
            approval_service.resolve_approval(action_id, False)
            
        task = asyncio.create_task(resolve_later())
        
        result = await approval_service.request_approval(
            action_type="test_action",
            details={},
            timeout=1.0
        )
        
        await task
        
        assert result is False

@pytest.mark.asyncio
async def test_approval_flow_timeout(approval_service):
    with patch("app.domain.services.approval_service.alfonso_bridge.send_command", new_callable=AsyncMock):
        
        # We don't resolve it, so it should timeout
        result = await approval_service.request_approval(
            action_type="test_action",
            details={},
            timeout=0.1
        )
        
        assert result is False
