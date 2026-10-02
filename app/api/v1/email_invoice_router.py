from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from app.domain.schemas import (
    InboxStatusDTO,
    EmailAccountConfigDTO,
    EmailSyncResultDTO,
    InvoiceApprovalProposalDTO,
    ApproveInvoiceProposalCommand,
    InvoiceApprovalResultDTO,
    InvoiceProcessingStatus,
)
from app.domain.services.email_sync_service import EmailSyncService
from app.infrastructure.database.repositories.invoice_proposal_repository import (
    InvoiceProposalRepository,
)

router = APIRouter(prefix="/api/v1/inbox", tags=["Inbox & Invoices Ingestion"])


def get_email_sync_service() -> EmailSyncService:
    return EmailSyncService()


@router.get("/status", response_model=InboxStatusDTO)
def get_inbox_status(service: EmailSyncService = Depends(get_email_sync_service)):
    """Retorna el estado de conexión del buzón de correo sin generar datos falsos."""
    return service.get_inbox_status()


@router.post("/config", response_model=InboxStatusDTO)
def configure_email_account(
    config: EmailAccountConfigDTO,
    service: EmailSyncService = Depends(get_email_sync_service)
):
    """Guarda o actualiza las credenciales de conexión IMAP."""
    try:
        service.configure_account(config)
        return service.get_inbox_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error al guardar credenciales: {str(e)}")


@router.post("/sync", response_model=EmailSyncResultDTO)
async def sync_inbox_emails(service: EmailSyncService = Depends(get_email_sync_service)):
    """Dispara la sincronización de correos no leídos y escaneo de facturas adjuntas."""
    status = service.get_inbox_status()
    if not status.is_connected:
        raise HTTPException(
            status_code=412,
            detail="Buzón no configurado: configure su cuenta de correo antes de sincronizar"
        )
    return await service.sync_emails()


@router.get("/proposals", response_model=List[InvoiceApprovalProposalDTO])
def list_invoice_proposals(status: Optional[str] = Query(default=None)):
    """Lista las propuestas de facturas extraídas."""
    return InvoiceProposalRepository.list_proposals(status=status)


@router.get("/proposals/{proposal_id}", response_model=InvoiceApprovalProposalDTO)
def get_invoice_proposal(proposal_id: str):
    """Obtiene el detalle completo de una propuesta de factura recibida."""
    prop = InvoiceProposalRepository.get_proposal(proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Propuesta no encontrada")
    return prop


@router.post("/proposals/{proposal_id}/approve", response_model=InvoiceApprovalResultDTO)
def approve_invoice_proposal(proposal_id: str, cmd: ApproveInvoiceProposalCommand):
    """Aplaza la aprobación a la orquestación contable."""
    from app.domain.services.received_invoice_accounting_service import ReceivedInvoiceAccountingService
    accounting_svc = ReceivedInvoiceAccountingService()
    try:
        return accounting_svc.approve_and_record_proposal(
            proposal_id=proposal_id,
            tenant_id=cmd.tenant_id,
            confirmed_pgc_account=cmd.confirmed_pgc_account,
            custom_concept=cmd.custom_concept,
            target_partner_account=cmd.target_partner_account
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/proposals/{proposal_id}/reject", response_model=InvoiceApprovalResultDTO)
def reject_invoice_proposal(proposal_id: str, reason: Optional[str] = None):
    """Descarta una propuesta de factura."""
    from app.domain.services.received_invoice_accounting_service import ReceivedInvoiceAccountingService
    accounting_svc = ReceivedInvoiceAccountingService()
    try:
        return accounting_svc.reject_proposal(proposal_id=proposal_id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
