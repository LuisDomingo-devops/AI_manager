import asyncio
import uuid
from typing import Dict, Any
from app.utils.logger import app_logger
from app.infrastructure.adapters.alfonso_bridge import bridge as alfonso_bridge

class ApprovalService:
    def __init__(self):
        self._pending_approvals: Dict[str, asyncio.Future] = {}

    async def request_approval(self, action_type: str, details: Dict[str, Any], timeout: float = 120.0) -> bool:
        """
        Request human approval for a sensitive action via the frontend.
        """
        action_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_approvals[action_id] = future

        app_logger.info(f"Solicitando aprobación OOB para {action_type} (ID: {action_id})")
        
        try:
            # Enviar solicitud al frontend
            await alfonso_bridge.send_command("approval_required", params={
                "action_id": action_id,
                "action_type": action_type,
                "details": details,
                "message": f"Se requiere confirmación para: {action_type}"
            })
            
            # Esperar resolución (confirm o reject)
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            app_logger.warning(f"Timeout esperando aprobación para {action_id}")
            return False
        finally:
            self._pending_approvals.pop(action_id, None)

    def resolve_approval(self, action_id: str, approved: bool) -> bool:
        """
        Resolve a pending approval. Called by the REST API endpoint.
        """
        if action_id in self._pending_approvals:
            future = self._pending_approvals[action_id]
            if not future.done():
                future.set_result(approved)
                app_logger.info(f"Aprobación OOB {action_id} resuelta: {'APROBADA' if approved else 'RECHAZADA'}")
                return True
        app_logger.warning(f"Intento de resolver aprobación desconocida o ya resuelta: {action_id}")
        return False

approval_service = ApprovalService()
