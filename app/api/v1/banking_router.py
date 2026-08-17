from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any
from pydantic import BaseModel

from app.api.routes import verify_api_key
from app.domain.services.bank_service import BankService

router = APIRouter(prefix="/banking", dependencies=[Depends(verify_api_key)])

class BankConnectionCreateRequest(BaseModel):
    alias: str
    provider: str
    bank_name: str
    iban: str
    credentials_json: Optional[str] = ""

@router.get("/connections")
async def list_connections_endpoint():
    """Lista las conexiones bancarias y su estado de consentimiento PSD2."""
    connections = BankService.list_connections()
    return {"status": "ok", "total": len(connections), "connections": connections}

@router.post("/connections")
async def create_connection_endpoint(req: BankConnectionCreateRequest):
    """Añade una nueva cuenta bancaria conectada con vigencia PSD2 a 180 días."""
    conn_id = BankService.add_connection(
        alias=req.alias,
        provider=req.provider,
        bank_name=req.bank_name,
        iban=req.iban,
        credentials_json=req.credentials_json or ""
    )
    return {"status": "ok", "connection_id": conn_id, "message": "Conexión bancaria añadida exitosamente."}

@router.get("/consent/{connection_id}")
async def check_consent_endpoint(connection_id: int):
    """Comprueba el estado y días restantes del consentimiento PSD2 (180 días)."""
    return BankService.check_consent_status(connection_id)
