from typing import Dict, Any
from app.utils.logger import tool_logger
from app.adapters.memory.asset_repository import MemoryAssetRepository
from app.domain.services.depreciation_service import DepreciationService
from app.infrastructure.database.memory.memory import tenant_context

async def add_asset(name: str, purchase_date: str, cost: float, salvage_value: float, useful_life_years: int) -> dict:
    """
    Registra un nuevo bien de inversión / inmovilizado.
    """
    try:
        repo = MemoryAssetRepository()
        client_id = tenant_context.get()
        asset_id = repo.save_asset(client_id, {
            "name": name,
            "purchase_date": purchase_date,
            "cost": cost,
            "salvage_value": salvage_value,
            "useful_life_years": useful_life_years
        })
        return {"status": "ok", "message": "Activo guardado correctamente.", "asset_id": asset_id}
    except Exception as e:
        tool_logger.exception("Error al añadir activo")
        return {"status": "error", "message": str(e)}

async def list_assets() -> dict:
    """
    Obtiene la lista de todos los bienes de inversión.
    """
    try:
        repo = MemoryAssetRepository()
        client_id = tenant_context.get()
        assets = repo.list_assets(client_id)
        return {"status": "ok", "assets": assets}
    except Exception as e:
        tool_logger.exception("Error al listar activos")
        return {"status": "error", "message": str(e)}

async def get_amortization_table(year: int) -> dict:
    """
    Obtiene el cuadro de amortización propuesto para un ejercicio contable.
    """
    try:
        repo = MemoryAssetRepository()
        ds = DepreciationService(repo)
        client_id = tenant_context.get()
        proposal = ds.calculate_depreciation_proposal(client_id, year)
        return {"status": "ok", "year": year, "proposal": proposal}
    except Exception as e:
        tool_logger.exception("Error al generar cuadro de amortización")
        return {"status": "error", "message": str(e)}

async def execute_amortization(year: int) -> dict:
    """
    Contabiliza (crea asiento) de las amortizaciones del año.
    """
    try:
        repo = MemoryAssetRepository()
        ds = DepreciationService(repo)
        client_id = tenant_context.get()
        res = ds.record_depreciation_entries(client_id, year)
        return res
    except Exception as e:
        tool_logger.exception("Error al contabilizar amortización")
        return {"status": "error", "message": str(e)}

TOOLS = {
    "add_asset": add_asset,
    "list_assets": list_assets,
    "get_amortization_table": get_amortization_table,
    "execute_amortization": execute_amortization,
}
