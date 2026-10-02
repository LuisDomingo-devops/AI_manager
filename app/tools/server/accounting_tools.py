"""
Herramientas contables MCP / Agente para Estados Financieros, Amortizaciones y Cierre Contable.
Conforme al PGC PYMES (RD 1515/2007) y Código de Comercio con control Human-in-the-Loop.
"""

from typing import Dict, Any, List
from app.domain.services.ledger_service import LedgerService
from app.domain.services.balance_sheet_pymes_service import BalanceSheetPymesService
from app.domain.services.income_statement_service import IncomeStatementService
from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine
from app.domain.services.fiscal_year_closing_service import FiscalYearClosingService
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
    Genera el Balance de Situación (Activo vs Pasivo + Patrimonio) normalizado PGC PYMES para un año.
    Garantiza el cuadre matemático al céntimo.
    """
    try:
        service = BalanceSheetPymesService()
        sheet = service.calculate_balance_sheet(tenant_id="default", fiscal_year=year)
        return {
            "status": "ok",
            "year": year,
            "balance": sheet.model_dump(),
            "is_balanced": sheet.is_balanced
        }
    except Exception as e:
        tool_logger.exception("Error al generar el Balance de Situación")
        return {"status": "error", "message": str(e)}


async def calculate_depreciation_proposal_tool(year: int) -> dict:
    """
    Calcula la propuesta de cuotas de amortización del ejercicio según tablas oficiales de la LIS.
    Aplica prorrata de adquisición y límite de valor residual.
    """
    try:
        engine = AssetDepreciationEngine()
        proposals = engine.calculate_depreciation_proposal(client_id="default", year=year)
        return {
            "status": "ok",
            "fiscal_year": year,
            "count": len(proposals),
            "proposals": [p.model_dump() for p in proposals]
        }
    except Exception as e:
        tool_logger.exception("Error al calcular la propuesta de amortización")
        return {"status": "error", "message": str(e)}


async def execute_depreciation_tool(year: int, confirmed_by_user: bool = False) -> dict:
    """
    Contabiliza las dotaciones a la amortización en el Libro Diario legal (cuentas 681/281).
    Requiere confirmación explícita (Human-in-the-Loop).
    """
    if not confirmed_by_user:
        return {
            "status": "error",
            "message": "Operación cancelada: se requiere confirmación explícita (confirmed_by_user=True) para contabilizar amortizaciones."
        }
    try:
        engine = AssetDepreciationEngine()
        res = engine.record_depreciation_entries(client_id="default", year=year)
        return {
            "status": res.status,
            "message": res.message,
            "journal_entry_id": res.journal_entry_id,
            "total_amount_amortized": float(res.total_amount_amortized),
            "is_posted": res.is_posted
        }
    except Exception as e:
        tool_logger.exception("Error al contabilizar amortizaciones")
        return {"status": "error", "message": str(e)}


async def simulate_closing_tool(year: int, corporate_tax_rate: float = 0.25) -> dict:
    """
    Simula el cierre contable del ejercicio: regularización a cuenta 129, saldado de balance y apertura N+1.
    """
    try:
        service = FiscalYearClosingService()
        simulation = service.simulate_year_end_closing(
            tenant_id="default",
            fiscal_year=year,
            corporate_tax_rate=corporate_tax_rate
        )
        return {
            "status": "ok",
            "fiscal_year": year,
            "simulation": simulation.model_dump()
        }
    except Exception as e:
        tool_logger.exception("Error al simular el cierre de ejercicio")
        return {"status": "error", "message": str(e)}


async def execute_closing_tool(year: int, confirmed_by_user: bool = False, corporate_tax_rate: float = 0.25) -> dict:
    """
    Ejecuta el cierre formal del ejercicio contable: regularización, cierre, inmutabilidad y apertura N+1.
    Requiere confirmación explícita HITL.
    """
    if not confirmed_by_user:
        return {
            "status": "error",
            "message": "Operación cancelada: el cierre del ejercicio contable requiere confirmación explícita (confirmed_by_user=True)."
        }
    try:
        service = FiscalYearClosingService()
        res = service.execute_year_end_closing(
            tenant_id="default",
            fiscal_year=year,
            corporate_tax_rate=corporate_tax_rate,
            closed_by="user_hitl"
        )
        return {
            "status": "ok",
            "message": res.message,
            "fiscal_year": res.fiscal_year,
            "next_fiscal_year": res.next_fiscal_year,
            "resultado_ejercicio": float(res.resultado_ejercicio),
            "asiento_regularizacion_id": res.asiento_regularizacion_id,
            "asiento_cierre_id": res.asiento_cierre_id,
            "asiento_apertura_id": res.asiento_apertura_id
        }
    except Exception as e:
        tool_logger.exception("Error al ejecutar el cierre contable")
        return {"status": "error", "message": str(e)}


TOOLS = {
    "get_libro_diario": get_libro_diario,
    "get_balance_situacion": get_balance_situacion,
    "calculate_depreciation_proposal_tool": calculate_depreciation_proposal_tool,
    "execute_depreciation_tool": execute_depreciation_tool,
    "simulate_closing_tool": simulate_closing_tool,
    "execute_closing_tool": execute_closing_tool,
}
