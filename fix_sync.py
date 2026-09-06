import os
routes_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\api\routes.py'

with open(routes_path, 'r', encoding='utf-8') as f:
    content = f.read()

sync_endpoint = """
@router.get("/dashboard/sync", summary="Obtiene todos los datos del dashboard en una sola llamada para evitar saturación.")
async def dashboard_sync(client_id: str = Depends(verify_api_key)):
    from app.domain.services.tax_parser_service import TaxParserService
    from app.adapters.calendar_db import list_events
    from app.domain.services.verifactu_service import VerifactuService
    import datetime
    
    # 1. Aggregates
    try:
        aggregates = TaxParserService.get_quarterly_aggregates()
    except Exception:
        aggregates = []
        
    # 2. Events (current month)
    try:
        today = datetime.date.today()
        start = today.replace(day=1)
        # next month
        if start.month == 12:
            end = start.replace(year=today.year+1, month=1)
        else:
            end = start.replace(month=today.month+1)
        events = list_events(start.isoformat(), end.isoformat())
    except Exception:
        events = []
        
    # 3. Compliance
    try:
        compliance = VerifactuService.get_compliance_declaration_dossier(client_id=client_id)
    except Exception:
        compliance = {}

    return {
        "status": "ok",
        "aggregates": aggregates,
        "events": events,
        "compliance": compliance,
        "customization": {} # Placeholder if needed
    }
"""

if "/dashboard/sync" not in content:
    # Add it before the # ── Routers ── section or at the end of the file.
    # Actually just add it to `router` which is defined as `router = APIRouter(prefix="")`
    # Let's insert it after `router = APIRouter(prefix="")`
    content = content.replace('router = APIRouter(prefix="")', 'router = APIRouter(prefix="")\n' + sync_endpoint)
    with open(routes_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("routes.py updated with /dashboard/sync")
else:
    print("Already there.")
