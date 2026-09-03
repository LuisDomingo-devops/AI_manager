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
    create_product,
    update_product,
    delete_product,
    get_contacts,
    create_contact,
    update_contact,
    delete_contact
)

router = APIRouter(prefix="/billing", dependencies=[Depends(verify_api_key)])

from app.domain.services.document_customization_service import DocumentCustomizationService
from app.adapters.document_customization import SqliteDocumentCustomizationAdapter
from app.adapters.memory.memory import tenant_context

customization_service = DocumentCustomizationService(SqliteDocumentCustomizationAdapter())

class LineItem(BaseModel):
    product_id: Optional[int] = None
    description_override: str
    quantity: int = 1
    unit_price: float
    subtotal: float

class InvoiceCreateRequest(BaseModel):
    client_name: str
    client_nif: str
    amount: float  # Base imponible total (backward compatibility)
    concept: str   # Concepto principal (backward compatibility)
    items: Optional[List[LineItem]] = None
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

class ProductCreateRequest(BaseModel):
    sku: Optional[str] = None
    name: str
    price: float
    description: str = ""
    iva_rate: float = 21.0
    item_type: str = "product"

class ProductUpdateRequest(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    iva_rate: Optional[float] = None
    stock: Optional[int] = None
    item_type: Optional[str] = None

class ContactCreateRequest(BaseModel):
    name: str
    nif: str
    email: str
    phone: str = ""
    address: str = ""
    iban: str = ""
    contact_type: str = "Cliente"

class ContactUpdateRequest(BaseModel):
    name: Optional[str] = None
    nif: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    iban: Optional[str] = None
    contact_type: Optional[str] = None


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
        confirmed_by_user=req.confirmed_by_user,
        items=[i.model_dump() for i in req.items] if req.items else None
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

@router.get("/contacts")
async def list_contacts_endpoint(include_deleted: bool = False, contact_type: Optional[str] = None):
    """Lista todos los contactos (clientes/proveedores)."""
    return await get_contacts(include_deleted=include_deleted, contact_type=contact_type)

@router.post("/contacts")
async def create_contact_endpoint(req: ContactCreateRequest):
    res = await create_contact(
        name=req.name,
        nif=req.nif,
        email=req.email,
        phone=req.phone,
        address=req.address,
        iban=req.iban,
        contact_type=req.contact_type
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.put("/contacts/{contact_id}")
async def update_contact_endpoint(contact_id: int, req: ContactUpdateRequest):
    res = await update_contact(
        contact_id=contact_id,
        name=req.name,
        nif=req.nif,
        email=req.email,
        phone=req.phone,
        address=req.address,
        iban=req.iban,
        contact_type=req.contact_type
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.delete("/contacts/{contact_id}")
async def delete_contact_endpoint(contact_id: int):
    res = await delete_contact(contact_id=contact_id)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.get("/products")
async def list_products_endpoint(include_deleted: bool = False):
    """Lista los productos y servicios del catálogo activos (Soft Delete)."""
    return await get_products(include_deleted=include_deleted)

@router.post("/products")
async def create_product_endpoint(req: ProductCreateRequest):
    """Crea un nuevo producto o servicio en el catálogo."""
    res = await create_product(
        sku=req.sku,
        name=req.name,
        price=req.price,
        description=req.description,
        iva_rate=req.iva_rate,
        item_type=req.item_type
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res
@router.put("/products/{sku}")
async def api_update_product(sku: str, req: ProductUpdateRequest, _=Depends(verify_api_key)):
    res = await update_product(
        sku=sku,
        name=req.name,
        price=req.price,
        description=req.description,
        iva_rate=req.iva_rate,
        stock=req.stock,
        item_type=req.item_type
    )
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.delete("/products/{sku}")
async def delete_product_endpoint(sku: str, confirmed_by_user: bool = False):
    """Elimina (Soft Delete) un producto o servicio por su SKU."""
    res = await delete_product(sku=sku, confirmed_by_user=confirmed_by_user)
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res


class CustomizationUpdateRequest(BaseModel):
    logo_base64: Optional[str] = None
    primary_color: str = Field("#1E293B")
    secondary_color: str = Field("#64748B")
    font_family: str = Field("Helvetica")
    layout_template: str = Field("classic")
    elements_layout: Optional[str] = None
    quote_elements_layout: Optional[str] = None
    logo_width: Optional[int] = 110


@router.get("/customization")
async def get_customization_endpoint():
    """Obtiene los datos de personalización de documentos para el inquilino."""
    cid = tenant_context.get() or "default"
    return customization_service.get_customization(cid)


@router.post("/customization")
async def update_customization_endpoint(req: CustomizationUpdateRequest):
    """Actualiza la personalización de documentos para el inquilino."""
    cid = tenant_context.get() or "default"
    try:
        customization_service.save_customization(cid, req.model_dump())
        return {"status": "ok", "message": "Personalización de documentos guardada correctamente."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

