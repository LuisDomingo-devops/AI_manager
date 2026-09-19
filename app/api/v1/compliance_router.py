from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.dehu_service import DEHUService
from app.adapters.memory.memory import tenant_context
from app.api.routes import verify_api_key

router = APIRouter(prefix="/compliance", dependencies=[Depends(verify_api_key)])

@router.get("/declaration")
async def get_declaration_dossier():
    """Retorna el Expediente Técnico y Declaración Responsable de Conformidad (Art. 13 Orden HAC/1177/2024)."""
    cid = tenant_context.get()
    return VerifactuService.get_compliance_declaration_dossier(client_id=cid)

@router.get("/verify-chain")
async def verify_chain_integrity_endpoint():
    """Comprueba la integridad criptográfica de la cadena de registros de facturación."""
    return VerifactuService.verify_chain_integrity()

@router.post("/dehu/upload")
async def upload_dehu_notification(file: UploadFile = File(...)):
    """
    Recibe un archivo PDF de una notificación de la DEHú, extrae su texto
    y delega su análisis legal a MarcosAgent.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="El archivo debe ser un PDF válido.")
        
    try:
        pdf_bytes = await file.read()
        analysis_result = await DEHUService.process_and_analyze_notification(pdf_bytes)
        return analysis_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error procesando la notificación: {str(e)}")

from app.domain.services.signature_service import SignatureService
from app.infrastructure.database.repositories.certificate_repository import CertificateRepository
from app.adapters.memory.memory import _get_connection
from fastapi import Form

@router.post("/certificate/software")
async def upload_software_certificate(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    """Sube un certificado P12/PFX para firma automatizada."""
    if not (file.filename.endswith(".p12") or file.filename.endswith(".pfx")):
        raise HTTPException(status_code=400, detail="El archivo debe ser .p12 o .pfx")
    try:
        p12_bytes = await file.read()
        conn = _get_connection()
        repo = CertificateRepository(conn)
        svc = SignatureService(repo)
        
        tenant_id = tenant_context.get()
        cert_id = svc.store_software_certificate(tenant_id, p12_bytes, password)
        return {"status": "ok", "cert_id": cert_id, "message": "Certificado guardado con éxito"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.domain.services.audit_ledger import AuditLedgerService
from fastapi import Query

@router.get("/audit/logs")
async def get_audit_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    Retorna el log de auditoría (Audit Ledger) paginado para el tenant actual.
    """
    tenant_id = tenant_context.get()
    try:
        logs = AuditLedgerService.get_logs(client_id=tenant_id, limit=limit, offset=offset)
        return {"items": logs, "limit": limit, "offset": offset}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo logs de auditoría: {str(e)}")
