import asyncio
import uuid
from enum import Enum
from typing import Dict, Any, Optional, Union
from app.utils.logger import app_logger
from app.infrastructure.adapters.alfonso_bridge import bridge as alfonso_bridge


class CriticalActionType(str, Enum):
    EMIT_INVOICE = "emit_invoice"
    RECTIFY_INVOICE = "rectify_invoice"
    CANCEL_INVOICE = "cancel_invoice"
    SUBMIT_TAX_MODEL = "submit_tax_model"
    RECONCILE_BANK_ENTRY = "reconcile_bank_entry"
    SEND_INVOICE_EMAIL = "send_invoice_email"
    PURGE_RECORDS = "purge_records"
    HUMAN_CONFIRMATION = "human_confirmation"


class ApprovalService:
    def __init__(self):
        self._pending_approvals: Dict[str, asyncio.Future] = {}
        self._approval_metadata: Dict[str, Dict[str, Any]] = {}

    async def request_approval(
        self_or_cls,
        action_type: Union[CriticalActionType, str],
        details: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        entity_id: Optional[str] = None,
        summary: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> bool:
        """
        Solicita aprobación humana para una acción sensible mediante la GUI/WebSocket.
        Soporta invocación como método de instancia y como método de clase/estático.
        """
        details = details or {}
        effective_timeout = timeout_seconds if timeout_seconds is not None else (timeout if timeout is not None else 120.0)
        action_str = action_type.value if isinstance(action_type, CriticalActionType) else str(action_type)

        if isinstance(self_or_cls, ApprovalService):
            self = self_or_cls
        else:
            return await approval_service.request_approval(
                action_type=action_type,
                details=details,
                timeout=effective_timeout,
                entity_id=entity_id,
                summary=summary
            )

        action_id = str(uuid.uuid4())
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending_approvals[action_id] = future
        self._approval_metadata[action_id] = {
            "action_type": action_str,
            "entity_id": entity_id,
            "summary": summary or f"Confirmación requerida para: {action_str}",
            "details": details
        }

        app_logger.info(f"Solicitando aprobación HITL para {action_str} (ID: {action_id})")

        try:
            cmd_result = await alfonso_bridge.send_command("approval_required", params={
                "approval_id": action_id,
                "action_id": action_id,
                "action_type": action_str,
                "entity_id": entity_id,
                "summary": summary or f"Confirmación requerida para: {action_str}",
                "details": details,
                "message": f"Se requiere confirmación para: {action_str}"
            })
            if isinstance(cmd_result, dict) and cmd_result.get("status") == "error":
                app_logger.warning(f"No se pudo enviar solicitud de aprobación OOB: {cmd_result.get('error')}")
                return False

            result = await asyncio.wait_for(future, timeout=effective_timeout)
            return result

        except asyncio.TimeoutError:
            app_logger.warning(f"Timeout esperando aprobación para {action_id}")
            return False
        finally:
            self._pending_approvals.pop(action_id, None)
            self._approval_metadata.pop(action_id, None)

    def resolve_approval(self, action_id: str, approved: bool, user_notes: Optional[str] = None) -> bool:
        """
        Resuelve una aprobación pendiente invocada desde el endpoint REST o la GUI.
        """
        if action_id in self._pending_approvals:
            future = self._pending_approvals[action_id]
            if not future.done():
                future.set_result(approved)
                app_logger.info(
                    f"Aprobación HITL {action_id} resuelta: {'APROBADA' if approved else 'RECHAZADA'}"
                    + (f" (Notas: {user_notes})" if user_notes else "")
                )
                return True
        app_logger.warning(f"Intento de resolver aprobación desconocida o ya resuelta: {action_id}")
        return False


approval_service = ApprovalService()
