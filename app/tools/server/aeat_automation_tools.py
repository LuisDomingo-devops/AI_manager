"""
AEAT AUTOMATION TOOLS — Herramientas para la automatización del Modelo 303 en la web de la AEAT.

¿QUÉ HACE?
Extrae los agregados trimestrales del usuario y proporciona métodos para rellenar
el borrador del Modelo 303 en una sesión local abierta del navegador.
"""

from typing import Optional, Dict, Any
from app.domain.services.tax_parser_service import TaxParserService
from app.utils.logger import tool_logger
import os

# Selectores para el Modelo 303 en la web de la AEAT (sujetos a cambios por la AEAT)
# Estos selectores corresponden a las casillas típicas del Modelo 303.
SELECTORS_303 = {
    "base_devengado_21": "input[id$='C01']",      # Casilla [01] Base imponible a tipo general (21%)
    "tipo_devengado_21": "input[id$='C02']",      # Casilla [02] Tipo (21%)
    "cuota_devengado_21": "input[id$='C03']",     # Casilla [03] Cuota devengada
    
    "base_deducible_int": "input[id$='C28']",     # Casilla [28] Gastos corrientes base imponible
    "cuota_deducible_int": "input[id$='C29']",    # Casilla [29] Gastos corrientes cuota deducible
}


async def get_aeat_aggregated_data(year: int, quarter: int) -> Dict[str, Any]:
    """
    Obtiene y formatea los datos agregados listos para el Modelo 303.
    """
    aggregates = TaxParserService.get_quarterly_aggregates(year=year)
    
    # Buscar el trimestre específico
    quarter_data = None
    for agg in aggregates:
        if agg["quarter"] == quarter:
            quarter_data = agg
            break
            
    if not quarter_data:
        # Retornar estructura por defecto con ceros si no hay datos
        quarter_data = {
            "year": year,
            "quarter": quarter,
            "income": {"base": 0.0, "iva": 0.0, "irpf": 0.0, "total": 0.0, "count": 0},
            "expense": {"base": 0.0, "iva": 0.0, "irpf": 0.0, "total": 0.0, "count": 0},
            "net_result": 0.0
        }
        
    return quarter_data


async def generate_modelo_303_autofill_script(year: int, quarter: int) -> dict:
    """
    Genera un script de JavaScript que el usuario puede ejecutar en la consola del navegador
    para autorellenar el formulario activo del Modelo 303 con los datos de facturación.
    """
    try:
        data = await get_aeat_aggregated_data(year, quarter)
        
        income_base = data["income"]["base"]
        income_iva = data["income"]["iva"]
        expense_base = data["expense"]["base"]
        expense_iva = data["expense"]["iva"]
        
        # Generar código JS para autocompletar
        js_code = f"""
        (function() {{
            console.log("Alfonso Autónomo: Iniciando autocompletado del Modelo 303...");
            
            function findField(casillaNumber) {{
                const padded = String(casillaNumber).padStart(2, '0');
                const selectors = [
                    `input[id$='C${{padded}}']`, `input[id$='C${{casillaNumber}}']`,
                    `input[name$='C${{padded}}']`, `input[name$='C${{casillaNumber}}']`,
                    `#C${{padded}}`, `#C${{casillaNumber}}`,
                    `input[aria-label*='Casilla ${{padded}}']`, `input[aria-label*='Casilla ${{casillaNumber}}']`,
                    `input[title*='Casilla ${{padded}}']`, `input[title*='Casilla ${{casillaNumber}}']`,
                    `input[data-casilla='${{padded}}']`, `input[data-casilla='${{casillaNumber}}']`
                ];
                for (const sel of selectors) {{
                    const el = document.querySelector(sel);
                    if (el) return el;
                }}
                
                // Fallback heurístico buscando etiquetas que mencionen la casilla
                const labels = Array.from(document.querySelectorAll('label, span, td, div, p, th'));
                const searchTerms = [`[${{padded}}]`, `[${{casillaNumber}}]`, `casilla ${{padded}}`, `casilla ${{casillaNumber}}`];
                for (const label of labels) {{
                    const text = label.textContent.toLowerCase();
                    if (searchTerms.some(term => text.includes(term))) {{
                        const input = label.querySelector('input') || 
                                      (label.nextElementSibling && label.nextElementSibling.querySelector('input')) ||
                                      (label.parentElement && label.parentElement.querySelector('input'));
                        if (input) return input;
                    }}
                }}
                return null;
            }}

            const fields = {{
                "base_21": {{ casilla: "01", value: "{income_base}" }},
                "tipo_21": {{ casilla: "02", value: "21" }},
                "cuota_21": {{ casilla: "03", value: "{income_iva}" }},
                "base_ded": {{ casilla: "28", value: "{expense_base}" }},
                "cuota_ded": {{ casilla: "29", value: "{expense_iva}" }}
            }};
            
            let filledCount = 0;
            for (const key in fields) {{
                const item = fields[key];
                const input = findField(item.casilla);
                if (input) {{
                    input.value = item.value;
                    // Disparar eventos para que Angular/React/Vue se enteren del cambio
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    console.log("Rellenado: " + key + " (Casilla " + item.casilla + ") = " + item.value);
                    filledCount++;
                }} else {{
                    console.warn("No se encontró la casilla: " + item.casilla);
                }}
            }}
            
            alert("Alfonso Autónomo: Se han rellenado " + filledCount + " casillas en el portal de la AEAT. Por favor, verifique el borrador del Modelo 303.");
        }})();
        """
        
        return {
            "status": "ok",
            "year": year,
            "quarter": quarter,
            "data_used": {
                "income_base": income_base,
                "income_iva": income_iva,
                "expense_base": expense_base,
                "expense_iva": expense_iva
            },
            "script": js_code.strip()
        }
    except Exception as e:
        tool_logger.exception("Error al generar script de autocompletado")
        return {"status": "error", "message": str(e)}


async def fill_modelo_303_playwright(year: int, quarter: int, headless: bool = False) -> dict:
    """
    Inicia una sesión de Playwright headed para guiar al usuario en el rellenado del Modelo 303.
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright no está instalado."}
        
    try:
        data = await get_aeat_aggregated_data(year, quarter)
        
        income_base = data["income"]["base"]
        income_iva = data["income"]["iva"]
        expense_base = data["expense"]["base"]
        expense_iva = data["expense"]["iva"]
        
        aeat_url = "https://sede.agenciatributaria.gob.es/Sede/procedimiento/G611.shtml"
        
        # Guardar en logs y notificar al usuario
        tool_logger.info(f"Abriendo navegador controlado para rellenar Modelo 303 Q{quarter} {year}")
        
        # Nota: No cerramos la sesión para permitir que el usuario interactúe
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(aeat_url)
        
        # Retornamos éxito y dejamos el navegador abierto
        # En un flujo interactivo real, el agente esperaría a que el usuario se autentique y llegue a la página
        # del formulario para inyectar los valores.
        return {
            "status": "ok",
            "message": f"Navegador abierto en la página del Modelo 303. Usa el script inyectable cuando estés dentro.",
            "data_used": {
                "income_base": income_base,
                "income_iva": income_iva,
                "expense_base": expense_base,
                "expense_iva": expense_iva
            }
        }
    except Exception as e:
        tool_logger.exception("Error en automatización con Playwright")
        return {"status": "error", "message": str(e)}


# Registro de herramientas del plugin
TOOLS = {
    "generate_modelo_303_autofill_script": generate_modelo_303_autofill_script,
    "fill_modelo_303_playwright": fill_modelo_303_playwright,
}
