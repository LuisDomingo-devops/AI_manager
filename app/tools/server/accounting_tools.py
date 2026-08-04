from typing import Dict, Any, List
from app.domain.services.ledger_service import LedgerService
from app.utils.logger import tool_logger

async def get_libro_diario(year: int) -> dict:
    """
    Retorna el Libro Diario completo en formato estructurado de partida doble (PGC) para un año.
    """
    try:
        diario = LedgerService.get_libro_diario(year)
        return {
            "status": "ok",
            "year": year,
            "count": len(diario),
            "diario": diario
        }
    except Exception as e:
        tool_logger.exception("Error al recuperar el Libro Diario")
        return {"status": "error", "message": str(e)}

async def get_balance_situacion(year: int) -> dict:
    """
    Genera el Balance de Situación (Activo vs Pasivo + Patrimonio) según el PGC para un año.
    """
    try:
        balance = LedgerService.get_balance_situacion(year)
        return {
            "status": "ok",
            "year": year,
            "balance": balance
        }
    except Exception as e:
        tool_logger.exception("Error al generar el Balance de Situación")
        return {"status": "error", "message": str(e)}

TOOLS = {
    "get_libro_diario": get_libro_diario,
    "get_balance_situacion": get_balance_situacion,
}
