import pytest
from app.domain.services.boe_reader import BOEReaderService
from app.domain.services.excel_sync import ExcelSyncService

def test_boe_reader_url():
    url = BOEReaderService.get_boe_sumario_url("20260803")
    assert url == "https://www.boe.es/diario_boe/xml.php?id=BOE-S-20260803"

def test_excel_sync_empty_or_valid():
    # Debería correr sin fallar y generar el archivo (aunque esté vacío de facturas)
    import os
    test_path = "data/test_facturas_sync.xlsx"
    if os.path.exists(test_path):
        os.remove(test_path)
    
    path = ExcelSyncService.sync_invoices_to_excel(test_path)
    assert os.path.exists(path)
    assert path == test_path
    
    # Limpiar
    if os.path.exists(test_path):
        os.remove(test_path)
