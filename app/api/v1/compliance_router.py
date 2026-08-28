from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.dehu_service import DEHUService
from app.adapters.memory.memory import tenant_context

router = APIRouter(prefix="/compliance")

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

