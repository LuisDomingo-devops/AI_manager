from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from typing import Optional
import json

from app.api.auth_deps import CurrentUser
from app.domain.services.import_service.a3_parser import A3Parser
from app.domain.services.import_service.contaplus_parser import ContaPlusParser
from app.domain.services.import_service.generic_parser import GenericParser
from app.domain.services.import_service.import_orchestrator import ImportOrchestrator

router = APIRouter(prefix="/import", tags=["Import"])

@router.post("/accounting")
async def import_accounting_data(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    mapping_config: Optional[str] = Form(None),
    current_user: str = CurrentUser
):
    """
    Imports historical accounting data from A3, ContaPlus, or Generic CSV.
    """
    content = await file.read()
    try:
        text_content = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text_content = content.decode("iso-8859-1")
        except Exception:
            raise HTTPException(status_code=400, detail="El archivo no es de texto legible.")
            
    source_type = source_type.upper()
    invoices = []
    
    if source_type == "A3":
        invoices = A3Parser.parse(text_content)
    elif source_type == "CONTAPLUS":
        invoices = ContaPlusParser.parse(text_content)
    elif source_type == "GENERIC_CSV":
        if not mapping_config:
            raise HTTPException(status_code=400, detail="mapping_config es obligatorio para GENERIC_CSV")
        try:
            mapping = json.loads(mapping_config)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="mapping_config debe ser un JSON válido")
        invoices = GenericParser.parse_csv(text_content, mapping)
    else:
        raise HTTPException(status_code=400, detail=f"source_type desconocido: {source_type}")
        
    if not invoices:
        return {"status": "ok", "message": "No se encontraron facturas válidas en el archivo.", "imported": 0}
        
    count = ImportOrchestrator.save_invoices(invoices)
    
    return {
        "status": "ok",
        "message": f"Se han importado {count} facturas correctamente.",
        "imported": count
    }
