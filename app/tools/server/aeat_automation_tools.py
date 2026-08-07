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
        
        aeat_url = "https://sede.agenciatributaria.gob.es/Sede/procedimiento/G322.shtml"
        
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


async def generate_modelo_130_autofill_script(year: int, quarter: int) -> dict:
    """
    Genera un script de JavaScript para autocompletar el borrador del Modelo 130 (IRPF autónomos)
    en la Sede Electrónica de la AEAT con los datos contables del trimestre.
    """
    try:
        data = await get_aeat_aggregated_data(year, quarter)
        income_base = data["income"]["base"]
        expense_base = data["expense"]["base"]
        net_result = data["net_result"]
        
        pago_fraccionado = max(0.0, net_result * 0.20)
        
        js_code = f"""
        (function() {{
            console.log("Alfonso Autónomo: Iniciando autocompletado del Modelo 130...");
            
            function findField(casillaNumber) {{
                const padded = String(casillaNumber).padStart(2, '0');
                const selectors = [
                    `input[id$='C${{padded}}']`, `input[id$='C${{casillaNumber}}']`,
                    `input[name$='C${{padded}}']`, `input[name$='C${{casillaNumber}}']`,
                    `#C${{padded}}`, `#C${{casillaNumber}}`
                ];
                for (const sel of selectors) {{
                    const el = document.querySelector(sel);
                    if (el) return el;
                }}
                return null;
            }}

            const fields = {{
                "ingresos_01": {{ casilla: "01", value: "{income_base}" }},
                "gastos_02": {{ casilla: "02", value: "{expense_base}" }},
                "rendimiento_03": {{ casilla: "03", value: "{net_result}" }},
                "pago_04": {{ casilla: "04", value: "{pago_fraccionado}" }},
                "resultado_19": {{ casilla: "19", value: "{pago_fraccionado}" }}
            }};
            
            let filledCount = 0;
            for (const key in fields) {{
                const item = fields[key];
                const input = findField(item.casilla);
                if (input) {{
                    input.value = item.value;
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    console.log("Rellenado: " + key + " (Casilla " + item.casilla + ") = " + item.value);
                    filledCount++;
                }}
            }}
            alert("Alfonso: Rellenado Modelo 130 (" + filledCount + " casillas). Por favor, verifique el borrador.");
        }})();
        """
        return {
            "status": "ok",
            "year": year,
            "quarter": quarter,
            "data_used": {
                "income_base": income_base,
                "expense_base": expense_base,
                "net_result": net_result,
                "pago_fraccionado": pago_fraccionado
            },
            "script": js_code.strip()
        }
    except Exception as e:
        tool_logger.exception("Error al generar script del Modelo 130")
        return {"status": "error", "message": str(e)}


async def generate_modelo_111_autofill_script(year: int, quarter: int) -> dict:
    """
    Genera un script para autocompletar el borrador del Modelo 111 (Retenciones de IRPF a profesionales/trabajadores).
    """
    try:
        data = await get_aeat_aggregated_data(year, quarter)
        expense_irpf = data["expense"]["irpf"]
        retention_count = data["expense"]["count"] if expense_irpf > 0 else 0
        
        js_code = f"""
        (function() {{
            console.log("Alfonso Autónomo: Iniciando autocompletado del Modelo 111...");
            function findField(c) {{ return document.querySelector(`input[id$='C${{c}}']`) || document.querySelector(`#C${{c}}`); }}
            
            const fields = {{
                "perceptores_07": {{ casilla: "07", value: "{retention_count}" }},
                "base_08": {{ casilla: "08", value: "{data["expense"]["base"] if expense_irpf > 0 else 0.0}" }},
                "retenciones_09": {{ casilla: "09", value: "{expense_irpf}" }},
                "total_28": {{ casilla: "28", value: "{expense_irpf}" }}
            }};
            
            let filled = 0;
            for(const k in fields) {{
                const input = findField(fields[k].casilla);
                if(input) {{
                    input.value = fields[k].value;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    filled++;
                }}
            }}
            alert("Alfonso: Rellenado Modelo 111 (" + filled + " casillas).");
        }})();
        """
        return {
            "status": "ok",
            "year": year,
            "quarter": quarter,
            "data_used": {
                "perceptores_count": retention_count,
                "retenciones_monto": expense_irpf
            },
            "script": js_code.strip()
        }
    except Exception as e:
        tool_logger.exception("Error al generar script del Modelo 111")
        return {"status": "error", "message": str(e)}


async def generate_modelo_390_summary(year: int) -> dict:
    """
    Genera el resumen contable anual necesario para la declaración informativa anual del IVA (Modelo 390).
    """
    try:
        aggregates = TaxParserService.get_quarterly_aggregates(year=year)
        
        total_income_base = 0.0
        total_income_iva = 0.0
        total_expense_base = 0.0
        total_expense_iva = 0.0
        
        for q in aggregates:
            total_income_base += q["income"]["base"]
            total_income_iva += q["income"]["iva"]
            total_expense_base += q["expense"]["base"]
            total_expense_iva += q["expense"]["iva"]
            
        result_anual = total_income_iva - total_expense_iva
        
        return {
            "status": "ok",
            "year": year,
            "summary": {
                "operaciones_interiores_devengadas_base": total_income_base,
                "operaciones_interiores_devengadas_iva": total_income_iva,
                "operaciones_interiores_deducibles_base": total_expense_base,
                "operaciones_interiores_deducibles_iva": total_expense_iva,
                "resultado_declaraciones_anual": result_anual
            }
        }
    except Exception as e:
        tool_logger.exception("Error al generar resumen del Modelo 390")
        return {"status": "error", "message": str(e)}


async def generate_modelo_115_autofill_script(year: int, quarter: int) -> dict:
    """
    Genera un script para autocompletar el borrador del Modelo 115 (Retenciones sobre alquileres de oficinas/locales).
    """
    try:
        data = await get_aeat_aggregated_data(year, quarter)
        rent_retention = data["expense"]["irpf"]
        perceptores = 1 if rent_retention > 0 else 0
        rent_base = data["expense"]["base"] if rent_retention > 0 else 0.0
        
        js_code = f"""
        (function() {{
            console.log("Alfonso: Iniciando autocompletado del Modelo 115...");
            function findField(c) {{ return document.querySelector(`input[id$='C${{c}}']`) || document.querySelector(`#C${{c}}`); }}
            
            const fields = {{
                "perceptores_01": {{ casilla: "01", value: "{perceptores}" }},
                "base_02": {{ casilla: "02", value: "{rent_base}" }},
                "retenciones_03": {{ casilla: "03", value: "{rent_retention}" }},
                "resultado_05": {{ casilla: "05", value: "{rent_retention}" }}
            }};
            
            let filled = 0;
            for(const k in fields) {{
                const input = findField(fields[k].casilla);
                if(input) {{
                    input.value = fields[k].value;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    filled++;
                }}
            }}
            alert("Alfonso: Rellenado Modelo 115 (" + filled + " casillas).");
        }})();
        """
        return {
            "status": "ok",
            "year": year,
            "quarter": quarter,
            "data_used": {
                "perceptores": perceptores,
                "base_retenciones": rent_base,
                "retenciones": rent_retention
            },
            "script": js_code.strip()
        }
    except Exception as e:
        tool_logger.exception("Error al generar script del Modelo 115")
        return {"status": "error", "message": str(e)}


async def generate_modelo_200_summary(year: int) -> dict:
    """
    Genera el resumen contable anual y estimación para el Impuesto sobre Sociedades (Modelo 200).
    """
    try:
        aggregates = TaxParserService.get_quarterly_aggregates(year=year)
        total_income = 0.0
        total_expense = 0.0
        for q in aggregates:
            total_income += q["income"]["base"]
            total_expense += q["expense"]["base"]
            
        profit = total_income - total_expense
        tax_estimate = max(0.0, profit * 0.25)
        
        return {
            "status": "ok",
            "year": year,
            "summary": {
                "total_ingresos": total_income,
                "total_gastos": total_expense,
                "resultado_antes_impuestos": profit,
                "tipo_impositivo": "25%",
                "estimacion_impuesto_sociedades": tax_estimate
            }
        }
    except Exception as e:
        tool_logger.exception("Error al generar resumen del Modelo 200")
        return {"status": "error", "message": str(e)}


async def generate_modelo_202_autofill_script(year: int, period: int) -> dict:
    """
    Genera un script para autocompletar el borrador del Modelo 202 (Pago fraccionado del Impuesto sobre Sociedades).
    """
    try:
        prev_year = year - 1
        data_prev = await generate_modelo_200_summary(prev_year)
        prev_tax = data_prev.get("summary", {}).get("estimacion_impuesto_sociedades", 0.0)
        pago_fraccionado = round(prev_tax * 0.18, 2)
        
        js_code = f"""
        (function() {{
            console.log("Alfonso: Iniciando autocompletado del Modelo 202...");
            const input = document.querySelector("input[id$='C01']") || document.querySelector("#C01");
            if (input) {{
                input.value = "{pago_fraccionado}";
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                alert("Alfonso: Rellenado Modelo 202 con pago fraccionado de {pago_fraccionado} €.");
            }} else {{
                alert("No se encontró la casilla principal de base de pago.");
            }}
        }})();
        """
        return {
            "status": "ok",
            "year": year,
            "period": f"{period}P",
            "data_used": {
                "base_ejercicio_anterior": prev_tax,
                "pago_fraccionado": pago_fraccionado
            },
            "script": js_code.strip()
        }
    except Exception as e:
        tool_logger.exception("Error al generar script del Modelo 202")
        return {"status": "error", "message": str(e)}


async def generate_modelo_347_summary(year: int) -> dict:
    """
    Identifica clientes o proveedores con volumen de operaciones superior a 3.005,06 € en el año fiscal (Modelo 347).
    """
    try:
        from app.adapters.memory.memory import _get_connection
        from app.utils.encryption import encryptor
        
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT issuer_name, issuer_nif, receiver_name, receiver_nif, total_amount, category FROM invoices WHERE year = ?", (year,))
            rows = cursor.fetchall()
            
        terceros = {}
        for r in rows:
            cat = r["category"]
            if cat in ("ingreso", "income"):
                name = encryptor.decrypt(r["receiver_name"])
                nif = encryptor.decrypt(r["receiver_nif"])
            else:
                name = encryptor.decrypt(r["issuer_name"])
                nif = encryptor.decrypt(r["issuer_nif"])
                
            total = float(encryptor.decrypt(r["total_amount"]))
            
            if nif not in terceros:
                terceros[nif] = {"name": name, "nif": nif, "total": 0.0, "category": cat}
            terceros[nif]["total"] += total
            
        reported_terceros = [t for t in terceros.values() if t["total"] > 3005.06]
        
        return {
            "status": "ok",
            "year": year,
            "limite_legal": 3005.06,
            "terceros_a_declarar": reported_terceros
        }
    except Exception as e:
        tool_logger.exception("Error al generar resumen del Modelo 347")
        return {"status": "error", "message": str(e)}


# Registro de herramientas del plugin
TOOLS = {
    "generate_modelo_303_autofill_script": generate_modelo_303_autofill_script,
    "fill_modelo_303_playwright": fill_modelo_303_playwright,
    "generate_modelo_130_autofill_script": generate_modelo_130_autofill_script,
    "generate_modelo_111_autofill_script": generate_modelo_111_autofill_script,
    "generate_modelo_390_summary": generate_modelo_390_summary,
    "generate_modelo_115_autofill_script": generate_modelo_115_autofill_script,
    "generate_modelo_200_summary": generate_modelo_200_summary,
    "generate_modelo_202_autofill_script": generate_modelo_202_autofill_script,
    "generate_modelo_347_summary": generate_modelo_347_summary,
}
