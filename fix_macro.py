import os
import re

# 1. Update tax_parser_tools.py
tax_parser_tools_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\tools\server\tax_parser_tools.py'
with open(tax_parser_tools_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add the new tool function
new_tool_func = """
async def get_full_financial_report(year: Optional[int] = None) -> dict:
    \"\"\"
    Obtiene un reporte financiero macro que incluye agregados trimestrales y el libro diario de forma simultánea.
    Útil para consultas genéricas sobre impuestos pagados, gastos y evolución contable en un mismo año.
    
    Parámetros:
    - year: Año opcional (ej. 2026).
    \"\"\"
    try:
        from app.domain.services.ledger_service import LedgerService
        tool_logger.info(f"Generando reporte financiero completo (macro-herramienta) para el año: {year or 'todos'}")
        
        aggregates = TaxParserService.get_quarterly_aggregates(year=year)
        libro_diario = []
        if year:
            libro_diario = LedgerService.get_libro_diario(year=year)
            
        return {
            "status": "ok",
            "year_filter": year,
            "aggregates": aggregates,
            "libro_diario": libro_diario
        }
    except Exception as e:
        tool_logger.exception("Error al calcular el reporte financiero completo")
        return {"status": "error", "message": f"Error al obtener el reporte: {str(e)}"}
"""

if "get_full_financial_report" not in content:
    content = content.replace("TOOLS = {", new_tool_func + "\n\n# Registro de herramientas exportado para la carga dinámica de plugins\nTOOLS = {")
    content = content.replace("    \"get_quarterly_aggregates\": get_quarterly_aggregates,", "    \"get_quarterly_aggregates\": get_quarterly_aggregates,\n    \"get_full_financial_report\": get_full_financial_report,")
    with open(tax_parser_tools_path, 'w', encoding='utf-8') as f:
        f.write(content)
        
print("tax_parser_tools.py updated.")

# 2. Update planner_orchestrator.py prompt
orchestrator_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\domain\planner_orchestrator.py'
with open(orchestrator_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Find SYSTEM_PROMPT or similar
if "get_full_financial_report" not in content:
    if "Eres Alfonso" in content:
        macro_prompt_injection = r"Si el usuario hace preguntas amplias o comparativas sobre impuestos, gastos o contabilidad de un año entero (ej. 'cuánto iva he pagado', 'muéstrame la evolución de gastos'), DEBES usar OBLIGATORIAMENTE la macro-herramienta 'get_full_financial_report' en lugar de llamar a agregados o libro diario por separado para ahorrar turnos.\\n"
        content = content.replace("Eres Alfonso", macro_prompt_injection + "Eres Alfonso")
        with open(orchestrator_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("planner_orchestrator.py updated with new prompt instruction.")
    else:
        print("SYSTEM PROMPT NOT FOUND in orchestrator!")
