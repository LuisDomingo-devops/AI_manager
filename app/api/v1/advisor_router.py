from fastapi import APIRouter, Depends
from typing import Optional

from app.api.routes import verify_api_key
from app.domain.services.ledger_service import LedgerService
from app.tools.server.billing_tools import export_advisor_pack_tool

router = APIRouter(prefix="/advisor", dependencies=[Depends(verify_api_key)])

@router.get("/pack/{year}")
async def get_advisor_pack_endpoint(year: int):
    """Consolida y exporta el paquete contable y fiscal completo para el asesor/gestoría."""
    return await export_advisor_pack_tool(year=year)
