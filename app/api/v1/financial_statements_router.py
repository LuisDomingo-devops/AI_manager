"""
Router FastAPI para Estados Financieros Oficiales, Amortizaciones y Cierre Contable PGC PYMES.
Conforme al RD 1515/2007 (PGC PYMES) para el depósito en el Registro Mercantil.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.routes import verify_api_key
from app.domain.schemas import (
    BalanceSheetDTO,
    IncomeStatementDTO,
    DepreciationRunResultDTO,
    YearEndClosingSimulationDTO,
    CloseFiscalYearExecutionCommand,
    CloseFiscalYearExecutionResultDTO,
)
from app.domain.services.balance_sheet_pymes_service import BalanceSheetPymesService
from app.domain.services.financial_statement_pdf_service import FinancialStatementPdfService
from app.domain.services.income_statement_service import IncomeStatementService
from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine
from app.domain.services.fiscal_year_closing_service import FiscalYearClosingService

router = APIRouter(prefix="/accounting", dependencies=[Depends(verify_api_key)])


@router.get(
    "/financial-statements/balance-sheet",
    response_model=BalanceSheetDTO,
    summary="Genera el Balance de Situación normalizado PGC PYMES"
)
async def get_balance_sheet_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal (ej. 2026)"),
    closing_date: Optional[str] = Query(None, description="Fecha de cierre (YYYY-MM-DD)"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Genera el Balance de Situación conforme al modelo oficial del RD 1515/2007."""
    service = BalanceSheetPymesService()
    try:
        sheet = service.calculate_balance_sheet(tenant_id=tenant_id, fiscal_year=fiscal_year, closing_date=closing_date)
        return sheet
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar el Balance de Situación: {str(e)}"
        )


@router.get(
    "/financial-statements/balance-sheet/pdf",
    summary="Exporta el Balance de Situación en PDF oficial para el Registro Mercantil"
)
async def get_balance_sheet_pdf_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal (ej. 2026)"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Genera el PDF oficial para depósito de cuentas en el Registro Mercantil."""
    balance_service = BalanceSheetPymesService()
    pdf_service = FinancialStatementPdfService()
    try:
        sheet = balance_service.calculate_balance_sheet(tenant_id=tenant_id, fiscal_year=fiscal_year)
        if not sheet.is_balanced:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="No se puede emitir el documento: el Balance de Situación no cumple la igualdad matemática patrimonial."
            )
        pdf_bytes = pdf_service.generate_balance_sheet_pdf(sheet)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=balance_situacion_{fiscal_year}.pdf"}
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al emitir el PDF del Balance: {str(e)}"
        )


@router.get(
    "/financial-statements/income-statement",
    response_model=IncomeStatementDTO,
    summary="Genera la Cuenta de Pérdidas y Ganancias (PyG) escalonada"
)
async def get_income_statement_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal (ej. 2026)"),
    quarter: Optional[int] = Query(None, ge=1, le=4, description="Trimestre (1-4, opcional)"),
    corporate_tax_rate: float = Query(0.25, ge=0.0, le=1.0, description="Tipo del Impuesto sobre Sociedades"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Genera la Cuenta de Pérdidas y Ganancias con márgenes escalonados."""
    service = IncomeStatementService()
    try:
        pyg = service.calculate_income_statement(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            quarter=quarter,
            corporate_tax_rate=corporate_tax_rate
        )
        return pyg
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar la Cuenta de Pérdidas y Ganancias: {str(e)}"
        )


@router.post(
    "/depreciation/calculate",
    summary="Calcula la propuesta de cuotas de amortización del ejercicio"
)
async def calculate_depreciation_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Calcula las cuotas de amortización del inmovilizado según tablas de la LIS."""
    from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine
    engine = AssetDepreciationEngine()
    try:
        proposal = engine.calculate_depreciation_proposal(client_id=tenant_id, year=fiscal_year)
        return {"fiscal_year": fiscal_year, "tenant_id": tenant_id, "proposals": proposal}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al calcular amortizaciones: {str(e)}"
        )


@router.post(
    "/depreciation/execute",
    summary="Contabiliza las dotaciones a la amortización en el Libro Diario"
)
async def execute_depreciation_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal"),
    confirmed_by_user: bool = Query(..., description="Autorización humana HITL"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Registra los asientos de amortización (cuentas 681/281) en el Libro Diario."""
    if not confirmed_by_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación cancelada: se requiere confirmación explícita (Human-in-the-Loop) para asentar amortizaciones."
        )
    from app.domain.services.asset_depreciation_engine import AssetDepreciationEngine
    engine = AssetDepreciationEngine()
    try:
        res = engine.record_depreciation_entries(client_id=tenant_id, year=fiscal_year)
        return res
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al contabilizar amortizaciones: {str(e)}"
        )


@router.post(
    "/closing/simulate",
    response_model=YearEndClosingSimulationDTO,
    summary="Simula el cierre contable del ejercicio sin persistir cambios"
)
async def simulate_closing_endpoint(
    fiscal_year: int = Query(..., description="Ejercicio fiscal"),
    corporate_tax_rate: float = Query(0.25, description="Tipo impositivo IS"),
    tenant_id: str = Query("default", description="Identificador del tenant/empresa")
):
    """Simula los asientos de regularización (129), cierre de balance y apertura del ejercicio siguiente."""
    service = FiscalYearClosingService()
    try:
        simulation = service.simulate_year_end_closing(
            tenant_id=tenant_id,
            fiscal_year=fiscal_year,
            corporate_tax_rate=corporate_tax_rate
        )
        return simulation
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al simular el cierre: {str(e)}"
        )


@router.post(
    "/closing/execute",
    response_model=CloseFiscalYearExecutionResultDTO,
    summary="Ejecuta de forma irrevocable el cierre contable del ejercicio"
)
async def execute_closing_endpoint(
    cmd: CloseFiscalYearExecutionCommand
):
    """Ejecuta el cierre formal: regularización, cierre de balance, inmutabilidad y apertura N+1."""
    if not cmd.confirmed_by_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operación cancelada: el cierre contable requiere confirmación explícita (Human-in-the-Loop)."
        )
    service = FiscalYearClosingService()
    try:
        result = service.execute_year_end_closing(
            tenant_id=cmd.tenant_id,
            fiscal_year=cmd.fiscal_year,
            corporate_tax_rate=cmd.corporate_tax_rate,
            closed_by=cmd.closed_by
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al ejecutar el cierre contable: {str(e)}"
        )
