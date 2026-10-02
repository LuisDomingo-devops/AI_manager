"""
tax_models_router.py
====================
Router FastAPI para el cálculo determinista de autoliquidaciones tributarias (303, 130, 111, 115, 390),
exportación a diseño de registro posicional oficial BOE (.ses/.txt), custodia legal de 5 años
y orquestación de la sesión asistida con Mozilla Firefox.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.api.routes import verify_api_key
from app.domain.services.tax_engine import TaxEngine
from app.domain.services.annual_tax_service import AnnualTaxService
from app.domain.services.boe_export_service import BoeExportService
from app.domain.services.tax_ledger_service import TaxLedgerService
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.models.billing import (
    Model303ResultDTO,
    Model130ResultDTO,
    Model111ResultDTO,
    Model115ResultDTO,
    Model390ResultDTO,
    BoeExportResultDTO,
    FirefoxFilingSessionDTO,
    TaxDeclarationAuditDTO,
    DeclarantInfoDTO
)
from app.domain.exceptions import TaxModelValidationError, BoeRecordFormattingError, FirefoxFilingError

router = APIRouter(prefix="/tax", dependencies=[Depends(verify_api_key)])


# --- Request Schemas ---

class Model303CalculateRequest(BaseModel):
    fiscal_year: int
    quarter: int = Field(..., ge=1, le=4)
    sales: List[Dict[str, Any]] = Field(default_factory=list)
    purchases: List[Dict[str, Any]] = Field(default_factory=list)
    prorrata_pct: float = Field(default=100.0, ge=0.0, le=100.0)
    compensacion_periodos_anteriores: float = Field(default=0.0, ge=0.0)


class Model130CalculateRequest(BaseModel):
    fiscal_year: int
    quarter: int = Field(..., ge=1, le=4)
    accumulated_incomes: float = Field(default=0.0)
    accumulated_expenses: float = Field(default=0.0)
    previous_payments: float = Field(default=0.0, ge=0.0)
    retentions_supported: float = Field(default=0.0, ge=0.0)
    deduction_art_80_bis: float = Field(default=0.0, ge=0.0)


class Model111CalculateRequest(BaseModel):
    fiscal_year: int
    quarter: int = Field(..., ge=1, le=4)
    work_withholdings: List[Dict[str, Any]] = Field(default_factory=list)
    prof_withholdings: List[Dict[str, Any]] = Field(default_factory=list)


class Model115CalculateRequest(BaseModel):
    fiscal_year: int
    quarter: int = Field(..., ge=1, le=4)
    rental_withholdings: List[Dict[str, Any]] = Field(default_factory=list)


class Model390CalculateRequest(BaseModel):
    fiscal_year: int
    quarterly_declarations: List[Dict[str, Any]] = Field(default_factory=list)
    prorrata_anual_pct: float = Field(default=100.0, ge=0.0, le=100.0)


class BoeExportRequest(BaseModel):
    fiscal_year: int
    period: str
    declarant_info: DeclarantInfoDTO
    model_data: Dict[str, Any]
    auto_record_ledger: bool = Field(default=True)


class FirefoxAssistedFilingRequest(BaseModel):
    model_code: str
    fiscal_year: int
    period: str
    boe_content: str
    use_sandbox: bool = Field(default=True)


# --- Endpoints User Story 1 (Cálculo Determinista) ---

@router.post("/models/303/calculate", response_model=Model303ResultDTO)
async def calculate_model_303_endpoint(req: Model303CalculateRequest):
    """Calcula la autoliquidación trimestral del Modelo 303 (IVA)."""
    engine = TaxEngine()
    return engine.calculate_model_303_from_data(
        fiscal_year=req.fiscal_year,
        quarter=req.quarter,
        sales=req.sales,
        purchases=req.purchases,
        prorrata_pct=req.prorrata_pct,
        compensacion_periodos_anteriores=req.compensacion_periodos_anteriores
    )


@router.post("/models/130/calculate", response_model=Model130ResultDTO)
async def calculate_model_130_endpoint(req: Model130CalculateRequest):
    """Calcula el pago fraccionado acumulativo del Modelo 130 (IRPF)."""
    engine = TaxEngine()
    return engine.calculate_model_130_from_data(
        fiscal_year=req.fiscal_year,
        quarter=req.quarter,
        accumulated_incomes=req.accumulated_incomes,
        accumulated_expenses=req.accumulated_expenses,
        previous_payments=req.previous_payments,
        retentions_supported=req.retentions_supported,
        deduction_art_80_bis=req.deduction_art_80_bis
    )


@router.post("/models/111/calculate", response_model=Model111ResultDTO)
async def calculate_model_111_endpoint(req: Model111CalculateRequest):
    """Calcula las retenciones sobre trabajo y profesionales para el Modelo 111."""
    engine = TaxEngine()
    return engine.calculate_model_111_from_data(
        fiscal_year=req.fiscal_year,
        quarter=req.quarter,
        work_withholdings=req.work_withholdings,
        prof_withholdings=req.prof_withholdings
    )


@router.post("/models/115/calculate", response_model=Model115ResultDTO)
async def calculate_model_115_endpoint(req: Model115CalculateRequest):
    """Calcula las retenciones sobre arrendamientos urbanos para el Modelo 115."""
    engine = TaxEngine()
    return engine.calculate_model_115_from_data(
        fiscal_year=req.fiscal_year,
        quarter=req.quarter,
        rental_withholdings=req.rental_withholdings
    )


@router.post("/models/390/calculate", response_model=Model390ResultDTO)
async def calculate_model_390_endpoint(req: Model390CalculateRequest):
    """Calcula la declaración resumen anual del IVA (Modelo 390)."""
    service = AnnualTaxService()
    return service.calculate_model_390(
        fiscal_year=req.fiscal_year,
        quarterly_declarations=req.quarterly_declarations,
        prorrata_anual_pct=req.prorrata_anual_pct
    )


# --- Endpoints User Story 2 (Exportación Oficial BOE) ---

@router.post("/models/{model_code}/export-boe", response_model=BoeExportResultDTO)
async def export_boe_endpoint(model_code: str, req: BoeExportRequest):
    """Genera el fichero de exportación telemática oficial del BOE (.ses/.txt)."""
    service = BoeExportService()
    export_res = service.export_model_boe(
        model_code=model_code,
        fiscal_year=req.fiscal_year,
        period=req.period,
        declarant_info=req.declarant_info,
        model_data=req.model_data
    )

    if req.auto_record_ledger:
        ledger = TaxLedgerService()
        ledger.save_declaration_filing(
            model_code=model_code,
            fiscal_year=req.fiscal_year,
            period=req.period,
            declarant_nif=req.declarant_info.nif,
            declarant_name=req.declarant_info.name,
            casillas_payload=req.model_data.get("casillas", {}),
            boe_file_content=export_res.content_raw,
            filing_status="EXPORTED"
        )

    return export_res


# --- Endpoints User Story 3 (Automatización Asistida Firefox) ---

@router.post("/filing/firefox/start-assisted-session", response_model=FirefoxFilingSessionDTO)
async def start_assisted_session_endpoint(req: FirefoxAssistedFilingRequest):
    """Inicia la sesión local asistida en Mozilla Firefox mediante Playwright."""
    service = FirefoxFilingService()
    session = await service.start_session(
        model_code=req.model_code,
        fiscal_year=req.fiscal_year,
        period=req.period,
        boe_content=req.boe_content,
        use_sandbox=req.use_sandbox
    )
    return await service.execute_assisted_workflow(session.session_id, req.boe_content)


@router.get("/filing/firefox/session/{session_id}", response_model=FirefoxFilingSessionDTO)
async def get_assisted_session_status_endpoint(session_id: str):
    """Consulta el estado de una sesión asistida en Firefox."""
    service = FirefoxFilingService()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Sesión '{session_id}' no encontrada.")
    return session


# --- Endpoints User Story 4 (Custodia Legal y Consulta Histórica por 5 Años) ---

@router.get("/filings", response_model=List[TaxDeclarationAuditDTO])
async def list_tax_filings_endpoint(
    model_code: Optional[str] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    tenant_id: str = Query("default")
):
    """Lista las declaraciones custodiadas dentro del plazo legal obligatorio de 5 años."""
    ledger = TaxLedgerService()
    return ledger.list_declarations(tenant_id=tenant_id, model_code=model_code, fiscal_year=fiscal_year)


@router.get("/filings/{filing_id}", response_model=TaxDeclarationAuditDTO)
async def get_tax_filing_detail_endpoint(filing_id: int):
    """Obtiene el detalle íntegro y casillas de una autoliquidación histórica."""
    ledger = TaxLedgerService()
    filing = ledger.get_declaration_by_id(filing_id)
    if not filing:
        raise HTTPException(status_code=404, detail=f"Declaración ID {filing_id} no encontrada.")
    return filing


@router.get("/filings/{filing_id}/download-boe")
async def download_boe_file_endpoint(filing_id: int):
    """Descarga el fichero oficial plano original (.ses) custodiado."""
    ledger = TaxLedgerService()
    filing = ledger.get_declaration_by_id(filing_id)
    if not filing:
        raise HTTPException(status_code=404, detail=f"Declaración ID {filing_id} no encontrada.")
    
    filename = f"{filing.model_code}_{filing.fiscal_year}_{filing.period}_{filing.declarant_nif}.ses"
    return Response(
        content=filing.boe_file_content,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
