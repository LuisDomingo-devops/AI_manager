from fastapi import APIRouter, Depends
from app.domain.services.verifactu_service import VerifactuService
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
