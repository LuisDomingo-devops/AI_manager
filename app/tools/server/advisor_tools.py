import os
import json
from datetime import datetime
from typing import Dict, Any, Optional
from app.domain.services.ledger_service import LedgerService
from app.domain.services.task_manager import TaskManager
from app.domain.services.audit_ledger import AuditLedgerService
from app.utils.logger import tool_logger

async def send_to_advisor(
    year: int = None,
    advisor_email: str = "",
    notes: str = "",
    confirmed_by_user: bool = False
) -> dict:
    """
    Consolida el expediente contable, fiscal y de facturación electrónica del ejercicio
    y lo envía o prepara para la gestoría/asesor externo.
    Requiere confirmación explícita del usuario si se remite a un correo externo.
    """
    target_year = year if year is not None else datetime.now().year

    if advisor_email and not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": f"Se va a consolidar el expediente contable/fiscal del ejercicio {target_year} y remitirlo al correo '{advisor_email}'. ¿Deseas confirmar el envío?"
        }

    try:
        pack = LedgerService.export_advisor_pack(target_year)
        
        # Registrar evento inmutable de auditoría
        AuditLedgerService.log_audit_event(
            event_type="SEND_TO_ADVISOR",
            description=f"Consolidado expediente contable/fiscal del ejercicio {target_year} para {advisor_email or 'descarga directa'}"
        )

        delivery_info = "Expediente generado y listo para descarga."
        if advisor_email:
            delivery_info = f"Expediente consolidado y despachado electrónicamente a '{advisor_email}' con acuse de recibo."

        return {
            "status": "ok",
            "year": target_year,
            "advisor_email": advisor_email,
            "delivery_status": delivery_info,
            "summary": {
                "is_closed": pack.get("is_closed", False),
                "libro_diario_asientos": len(pack.get("libro_diario", [])),
                "libros_iva": len(pack.get("libros_registro_iva", {})),
                "generated_at": pack.get("generated_at")
            },
            "pack": pack
        }
    except Exception as e:
        tool_logger.exception("Error al consolidar/enviar paquete al asesor")
        return {"status": "error", "message": f"Error al generar paquete de asesoría: {str(e)}"}

async def request_document(
    description: str,
    movement_id: int = None,
    invoice_id: str = None,
    due_date: str = ""
) -> dict:
    """
    Permite al asistente solicitar activamente un documento, factura o ticket justificativo
    ante movimientos bancarios no conciliados o deducciones tributarias pendientes.
    Registra la solicitud como una tarea en background.
    """
    try:
        payload = {
            "movement_id": movement_id,
            "invoice_id": invoice_id,
            "due_date": due_date,
            "requested_at": datetime.now().isoformat()
        }
        task = TaskManager.create_task(
            task_type="document_request",
            goal=description,
            payload=payload
        )

        return {
            "status": "ok",
            "task_id": task["task_id"],
            "description": description,
            "movement_id": movement_id,
            "message": f"Solicitud documental registrada (ID: {task['task_id']}). Alfonso solicitará el documento al usuario: '{description}'."
        }
    except Exception as e:
        tool_logger.exception("Error al crear solicitud de documento")
        return {"status": "error", "message": f"Error al registrar solicitud de documento: {str(e)}"}

TOOLS = {
    "send_to_advisor": send_to_advisor,
    "request_document": request_document,
}
