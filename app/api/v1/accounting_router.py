from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel

from app.api.routes import verify_api_key
from app.domain.services.ledger_service import LedgerService
from app.tools.server.billing_tools import get_profit_and_loss_report, close_fiscal_year_tool

router = APIRouter(prefix="/accounting", dependencies=[Depends(verify_api_key)])

class CloseYearRequest(BaseModel):
    year: int
    confirmed_by_user: bool = False

@router.get("/journal")
async def get_journal_endpoint(year: Optional[int] = None):
    """Consulta el Libro Diario oficial del PGC."""
    target_year = year or LedgerService.load_current_year()
    entries = LedgerService.get_libro_diario(target_year)
    return {"status": "ok", "year": target_year, "total_entries": len(entries), "journal": entries}

@router.get("/balance")
async def get_balance_endpoint(year: Optional[int] = None):
    """Consulta el Balance de Situación (Activos vs Pasivos y Patrimonio)."""
    target_year = year or LedgerService.load_current_year()
    balance = LedgerService.get_balance_situacion(target_year)
    return {"status": "ok", "year": target_year, "balance": balance}

@router.get("/profit-loss")
async def get_profit_loss_endpoint(year: Optional[int] = None, quarter: Optional[int] = None):
    """Consulta la Cuenta de Pérdidas y Ganancias (PyG / P&L) oficial."""
    return await get_profit_and_loss_report(year=year, quarter=quarter)

@router.post("/close-year")
async def close_year_endpoint(req: CloseYearRequest):
    """Ejecuta el cierre de ejercicio, regularización de cuentas 6/7 y bloqueo post-cierre."""
    return await close_fiscal_year_tool(year=req.year, confirmed_by_user=req.confirmed_by_user)
