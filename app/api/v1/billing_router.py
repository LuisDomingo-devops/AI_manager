from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.api.routes import verify_api_key
from app.domain.services.invoice_repository import InvoiceRepository
from app.domain.services.b2b_einvoice_service import B2BEInvoiceService
from app.tools.server.billing_tools import (
    generate_invoice_pdf,
    create_rectificativa_invoice,
    export_einvoice_tool,
    update_b2b_invoice_status_tool,
    get_b2b_invoice_status_history_tool,
    get_clients,
    create_client,
    get_products,
    create_product
)

router = APIRouter(prefix="/billing", dependencies=[Depends(verify_api_key)])

class InvoiceCreateRequest(BaseModel):
    client_name: str
    client_nif: str
    amount: float
    concept: str
    iva_rate: float = 21.0
    irpf_rate: float = 0.0
    confirmed_by_user: bool = False

class RectificativaCreateRequest(BaseModel):
    original_invoice_id: str
    rectificativa_type: str = "R1"
    rectification_reason: str
    base_imponible_rectificada: float
    iva_rate: float = 21.0
    irpf_rate: float = 0.0
    concept: str = "Factura Rectificativa"
    confirmed_by_user: bool = False

class B2BStatusUpdateRequest(BaseModel):
    invoice_id: str
    status: str
    reason: Optional[str] = None
    payment_date: Optional[str] = None
    payment_method: Optional[str] = None

@router.get("/invoices")
async def list_invoices(year: Optional[int] = None):
    """Lista todas las facturas emitidas y recibidas del inquilino."""
    invoices = InvoiceRepository.find_all_invoices()
    if year is not None:
        invoices = [inv for inv in invoices if inv.get("year") == year]
    return {"status": "ok", "total": len(invoices), "invoices": invoices}

@router.post("/invoices/create")
async def create_invoice_endpoint(req: InvoiceCreateRequest):
    """Crea una factura ordinaria y genera su registro Veri*Factu y PDF."""
    res = await generate_invoice_pdf(
        client_name=req.client_name,
        client_nif=req.client_nif,
        amount=req.amount,
        concept=req.concept,
        iva_rate=req.iva_rate,
        irpf_rate=req.irpf_rate,
        confirmed_by_user=req.confirmed_by_user
    )
    return res

@router.post("/invoices/rectificativa")
async def create_rectificativa_endpoint(req: RectificativaCreateRequest):
    """Emite una factura rectificativa con serie R-YYYY-XXX y vínculo a la original."""
    res = await create_rectificativa_invoice(
        original_invoice_id=req.original_invoice_id,
        rectificativa_type=req.rectificativa_type,
        rectification_reason=req.rectification_reason,
        base_imponible_rectificada=req.base_imponible_rectificada,
        iva_rate=req.iva_rate,
        irpf_rate=req.irpf_rate,
        concept=req.concept,
        confirmed_by_user=req.confirmed_by_user
    )
    return res

@router.get("/einvoice/export/{invoice_id}")
async def export_einvoice_endpoint(invoice_id: str, format_type: str = "ubl"):
    """Exporta la factura a XML estándar europeo EN 16931 (UBL 2.1) o Facturae 3.2.2."""
    return await export_einvoice_tool(invoice_id=invoice_id, format_type=format_type)

@router.post("/b2b/status")
async def update_b2b_status_endpoint(req: B2BStatusUpdateRequest):
    """Actualiza el estado comercial B2B conforme a la Ley Crea y Crece 18/2022."""
    return await update_b2b_invoice_status_tool(
        invoice_id=req.invoice_id,
        new_status=req.status,
        reason=req.reason,
        payment_date=req.payment_date,
        payment_method=req.payment_method
    )

@router.get("/b2b/history/{invoice_id}")
async def get_b2b_history_endpoint(invoice_id: str):
    """Obtiene la trazabilidad e historial cronológico de estados B2B de una factura."""
    return await get_b2b_invoice_status_history_tool(invoice_id=invoice_id)

@router.get("/clients")
async def list_clients_endpoint(include_deleted: bool = False):
    """Lista los clientes activos del catálogo (Soft Delete)."""
    return await get_clients(include_deleted=include_deleted)

@router.get("/products")
async def list_products_endpoint(include_deleted: bool = False):
    """Lista los productos y servicios del catálogo activos (Soft Delete)."""
    return await get_products(include_deleted=include_deleted)
