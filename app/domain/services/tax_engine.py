import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Any
from app.utils.logger import app_logger
from app.domain.services.tax_territory_factory import TaxTerritoryFactory

# Expresiones regulares para NIF español (A1234567B, 12345678Z, etc.)
NIF_REGEX = re.compile(r'\b([A-HJ-NP-SUVWXY]\d{7}[A-Z\d]|\d{8}[A-Z])\b', re.IGNORECASE)

# Expresiones regulares para fechas comunes
DATE_REGEX = re.compile(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b')
DATE_ISO_REGEX = re.compile(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b')

# Expresiones regulares para importes
MONEY_REGEX = re.compile(r'\b\d+(?:[.,]\d{2})?\b')

class TaxEngine:
    def __init__(self, tax_rules_port=None):
        self.tax_rules_port = tax_rules_port

    @classmethod
    def determine_document_type(cls, text: str) -> str:
        """
        Determina de forma determinista la tipología del documento usando expresiones regulares
        y heurísticas de palabras clave.
        Retorna: "Factura ordinaria", "Factura simplificada", "Albarán", o "Proforma"
        """
        text_upper = text.upper()
        
        # Prioridad 1: Proformas / Presupuestos
        if re.search(r'\b(PROFORMA|PRESUPUESTO|PRO-FORMA|ESTIMATION|QUOTE)\b', text_upper):
            return "Proforma"
            
        # Prioridad 2: Albaranes / Notas de Entrega
        if re.search(r'\b(ALBAR[AÁ]N|NOTA DE ENTREGA|DELIVERY NOTE|PACKING SLIP)\b', text_upper):
            if not re.search(r'\b(FACTURA|INVOICE)\b', text_upper):
                return "Albarán"
                
        # Prioridad 3: Tickets / Facturas simplificadas
        if re.search(r'\b(FACTURA SIMPLIFICADA|TICKET|RECIBO)\b', text_upper):
            return "Factura simplificada"
            
        # Por defecto, asumimos factura ordinaria si no encaja en las anteriores
        return "Factura ordinaria"

    @classmethod
    def determine_payment_direction(cls, text: str, user_nif: str, extracted_issuer_nif: str, extracted_receiver_nif: str) -> str:
        """
        Determina determinísticamente si el documento es a cobrar (income) o a pagar (expense).
        """
        user_nif_upper = user_nif.upper().strip()
        issuer_nif_upper = extracted_issuer_nif.upper().strip()
        receiver_nif_upper = extracted_receiver_nif.upper().strip()

        # 1. Validación estricta por NIFs extraídos
        if receiver_nif_upper == user_nif_upper:
            return "expense"
        elif issuer_nif_upper == user_nif_upper:
            return "income"
            
        # 2. Validación de respaldo buscando el NIF del usuario explícitamente en el texto
        text_upper = text.upper()
        if user_nif_upper in text_upper:
            if re.search(rf'\b(CLIENTE|FACTURADO A|RECEPTOR|BILL TO)[\s\S]{{0,100}}{re.escape(user_nif_upper)}\b', text_upper):
                return "expense"
            if re.search(rf'\b(EMISOR|PROVEEDOR|FACTURADO POR|FROM)[\s\S]{{0,100}}{re.escape(user_nif_upper)}\b', text_upper):
                return "income"
                
        # 3. Fallback: la mayoría de documentos subidos por un autónomo suelen ser gastos (tickets, compras)
        return "expense"

    def load_rules(self, date: str = None) -> Dict[str, Any]:
        """Carga las reglas fiscales aplicables a una fecha usando el puerto."""
        if not self.tax_rules_port:
            # Fallback en caso de que no se haya inyectado
            from app.infrastructure.adapters.file_tax_rules_adapter import FileTaxRulesAdapter
            self.tax_rules_port = FileTaxRulesAdapter()
        return self.tax_rules_port.get_rules(date=date)

    def update_tax_rules(self, new_rules: Dict[str, Any], boe_link: str, boe_section: str, confirmed_by_user: bool = False) -> Dict[str, Any]:
        """
        Actualiza las reglas fiscales tras confirmación humana.
        """
        # Validar enlace obligatorio del BOE y sección
        if not boe_link or not boe_link.startswith("http"):
            return {"status": "error", "message": "Es obligatorio proporcionar un enlace web directo y válido al documento del BOE."}
        if not boe_section or len(boe_section.strip()) < 3:
            return {"status": "error", "message": "Es obligatorio citar el artículo, sección o página específica del BOE que respalda la norma."}

        current_rules = self.load_rules()
        proposed = {**current_rules, **new_rules}
        
        # Identificar qué cambia
        changes = []
        for k, v in new_rules.items():
            if k in current_rules and current_rules[k] != v:
                changes.append(f"{k}: {current_rules[k]}% -> {v}%")
            elif k not in current_rules:
                changes.append(f"{k}: -> {v}%")

        if not changes:
            return {"status": "ok", "message": "No se especificaron cambios sobre las tasas fiscales vigentes."}

        if not confirmed_by_user:
            return {
                "status": "pending_confirmation",
                "message": (
                    f"Propuesta de actualización de tasas fiscales detectada:\n"
                    f"Cambios:\n" + "\n".join([f"- {c}" for c in changes]) + "\n"
                    f"Respaldado por BOE: {boe_link} (Sección: {boe_section})\n\n"
                    f"Por favor, confirme explícitamente para aplicar estos cambios (confirmed_by_user=True)."
                ),
                "proposed_rules": proposed,
                "boe_link": boe_link,
                "boe_section": boe_section
            }

        # Guardar a través del puerto
        try:
            proposed["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            proposed["boe_reference"] = f"{boe_link} ({boe_section})"
            
            if not self.tax_rules_port:
                from app.infrastructure.adapters.file_tax_rules_adapter import FileTaxRulesAdapter
                self.tax_rules_port = FileTaxRulesAdapter()
                
            self.tax_rules_port.save_rules(proposed)
            return {
                "status": "ok",
                "message": f"Reglas fiscales actualizadas exitosamente con los cambios: {', '.join(changes)}. Referencia del BOE guardada.",
                "rules": proposed
            }
        except Exception as e:
            return {"status": "error", "message": f"Error interno al actualizar reglas fiscales: {str(e)}"}

    @classmethod
    def parse_number(cls, val_str: str) -> float:
        """Limpia y parsea una cadena de texto en un número de coma flotante (soporta formatos ES y EN)."""
        val_str = re.sub(r'[^\d.,]', '', val_str).strip()
        if not val_str:
            return 0.0

        last_dot = val_str.rfind('.')
        last_comma = val_str.rfind(',')

        if last_dot != -1 and last_comma != -1:
            if last_dot > last_comma:
                # Formato anglosajón: 1,234.56 -> eliminar comas
                val_str = val_str.replace(',', '')
            else:
                # Formato europeo: 1.234,56 -> eliminar puntos y cambiar coma por punto
                val_str = val_str.replace('.', '').replace(',', '.')
        elif last_comma != -1:
            # Solo comas: si hay varias (1,000,000) o si tiene 2 decimales (1234,56)
            parts = val_str.split(',')
            if len(parts) == 2:
                val_str = val_str.replace(',', '.')
            else:
                val_str = val_str.replace(',', '')
        elif last_dot != -1:
            # Solo puntos: si tiene 3 dígitos al final y más partes (1.000)
            parts = val_str.split('.')
            if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3 and int(parts[0]) > 0):
                val_str = val_str.replace('.', '')

        try:
            return float(val_str)
        except ValueError:
            return 0.0

    @classmethod
    def resolve_dates(cls, text: str) -> Tuple[str, int, int]:
        """
        Busca y resuelve la fecha de la factura resolviendo el año y el trimestre contable.
        """
        date_str = None
        now = datetime.now()
        
        # 1. Intentar buscar fecha de emisión explícita primero
        emision_match = re.search(r'(?:fecha(?:\s+de)?\s+(?:emisi[oó]n|factura|cargo)|fecha)[\s:]*(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b', text, re.IGNORECASE)
        if emision_match:
            d, m, y = emision_match.groups()
            if len(y) == 2:
                y = "20" + y
            date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        else:
            emision_iso_match = re.search(r'(?:fecha(?:\s+de)?\s+(?:emisi[oó]n|factura|cargo)|fecha)[\s:]*(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b', text, re.IGNORECASE)
            if emision_iso_match:
                yyyy, mm, dd = emision_iso_match.groups()
                date_str = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"

        # 2. Fallback heurístico a la primera fecha libre
        if not date_str:
            iso_match = DATE_ISO_REGEX.search(text)
            if iso_match:
                yyyy, mm, dd = iso_match.groups()
                date_str = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
            else:
                std_match = DATE_REGEX.search(text)
                if std_match:
                    d, m, y = std_match.groups()
                    if len(y) == 2:
                        y = "20" + y
                    date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return date_str, dt.year, (dt.month - 1) // 3 + 1
            except ValueError:
                pass

        # Fallback a la fecha actual
        return now.strftime("%Y-%m-%d"), now.year, (now.month - 1) // 3 + 1

    @classmethod
    def extract_financials(cls, text: str, text_lower: str, iva_rate: float, irpf_rate: float) -> Tuple[float, float, float, float]:
        """
        Extrae base_imponible, iva_amount, irpf_amount y total_amount del texto de forma estructurada.
        """
        base_imponible = 0.0
        total_amount = 0.0

        # Buscar total de forma prioritaria
        total_matches = re.findall(r'\b(?:total|importe total|a pagar|total factura)\b\s*(?:[a-z\s]{0,12})?[\s:]*([0-9.,]+)\s*(?:€|eur|usd|\b)', text_lower)
        if total_matches:
            for m in reversed(total_matches):
                val = cls.parse_number(m)
                if val > 0:
                    total_amount = val
                    break

        # Buscar base imponible
        base_matches = re.findall(r'\b(?:base imponible|subtotal|base|neto)\b\s*(?:[a-z\s]{0,12})?[\s:]*([0-9.,]+)\s*(?:€|eur|usd|\b)', text_lower)
        if base_matches:
            for m in reversed(base_matches):
                val = cls.parse_number(m)
                if val > 0:
                    base_imponible = val
                    break

        # Si no encontramos base ni total, buscar el número mayor en el texto como Total
        if base_imponible == 0.0 and total_amount == 0.0:
            numbers = []
            for m in re.finditer(r'\b\d{1,3}(?:\.\d{3})*(?:,\d{2})\b|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b|\b\d+(?:[.,]\d{2})\b', text):
                val = cls.parse_number(m.group(0))
                if val > 0:
                    numbers.append(val)
        # Buscar importe explícito de retención IRPF si existe (ignorando porcentajes como 15% o (-15%))
        explicit_irpf = 0.0
        irpf_amt_matches = re.findall(r'(?:retenci[oó]n|irpf)(?:[^\d\n]*\d+\s*%\)?)?[\s:]*[-]?\s*([0-9.,]+)\s*(?:€|eur|\b)', text_lower)
        if irpf_amt_matches:
            for m in reversed(irpf_amt_matches):
                val = cls.parse_number(m)
                if val > 0:
                    explicit_irpf = val
                    break

        return cls.recalculate_and_validate(base_imponible, iva_rate, irpf_rate, total_amount, explicit_irpf=explicit_irpf)

    @classmethod
    def recalculate_and_validate(cls, base_imponible: float, iva_rate: float, irpf_rate: float, total_amount: float, explicit_irpf: float = 0.0) -> Tuple[float, float, float, float]:
        """
        Recalcula los importes para asegurar consistencia aritmética estricta.
        """
        iva_amount = 0.0
        irpf_amount = explicit_irpf if explicit_irpf > 0 else 0.0

        if base_imponible > 0.0 and total_amount == 0.0:
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            if irpf_amount == 0.0:
                irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)
            total_amount = round(base_imponible + iva_amount - irpf_amount, 2)
        elif total_amount > 0.0 and base_imponible > 0.0:
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            if irpf_amount == 0.0:
                irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)
        elif total_amount > 0.0 and base_imponible == 0.0:
            divisor = 1.0 + (iva_rate / 100.0) - (irpf_rate / 100.0)
            base_imponible = round(total_amount / divisor, 2)
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            if irpf_amount == 0.0:
                irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)

        # Reglas aritméticas estrictas
        expected_total = round(base_imponible + iva_amount - irpf_amount, 2)
        if abs(total_amount - expected_total) > 0.05:
            total_amount = expected_total

        return base_imponible, iva_amount, irpf_amount, total_amount

    @classmethod
    def get_fiscal_deadlines(cls, start_date: str, end_date: str) -> list:
        """
        Genera dinámicamente las obligaciones fiscales del autónomo español
        en el rango YYYY-MM-DD.
        """
        try:
            start_yr = int(start_date[:4])
            end_yr = int(end_date[:4])
        except Exception:
            start_yr = datetime.now().year
            end_yr = start_yr

        deadlines = []
        for yr in range(start_yr, end_yr + 1):
            # Trimestrales Q1, Q2, Q3, Q4
            quarters = [
                {
                    "quarter": 1,
                    "deadline_303_130": f"{yr}-04-20 23:59",
                    "deadline_111_115": f"{yr}-04-20 23:59",
                },
                {
                    "quarter": 2,
                    "deadline_303_130": f"{yr}-07-20 23:59",
                    "deadline_111_115": f"{yr}-07-20 23:59",
                },
                {
                    "quarter": 3,
                    "deadline_303_130": f"{yr}-10-20 23:59",
                    "deadline_111_115": f"{yr}-10-20 23:59",
                },
                {
                    "quarter": 4,
                    "deadline_303_130": f"{yr+1}-01-30 23:59",
                    "deadline_111_115": f"{yr+1}-01-20 23:59",
                }
            ]

            for q in quarters:
                deadlines.append({
                    "id": f"fiscal-303-q{q['quarter']}-{yr}",
                    "title": f"AEAT: Presentar Modelo 303 (IVA) Q{q['quarter']}",
                    "start_time": q["deadline_303_130"],
                    "end_time": q["deadline_303_130"],
                    "description": f"Autoliquidación del Impuesto sobre el Valor Añadido (IVA) correspondiente al Q{q['quarter']} de {yr}.",
                    "location": "Sede Electrónica AEAT",
                    "attendees": None
                })
                deadlines.append({
                    "id": f"fiscal-130-q{q['quarter']}-{yr}",
                    "title": f"AEAT: Presentar Modelo 130 (IRPF) Q{q['quarter']}",
                    "start_time": q["deadline_303_130"],
                    "end_time": q["deadline_303_130"],
                    "description": f"Pago fraccionado del IRPF para autónomos en estimación directa correspondiente al Q{q['quarter']} de {yr}.",
                    "location": "Sede Electrónica AEAT",
                    "attendees": None
                })
                deadlines.append({
                    "id": f"fiscal-111-q{q['quarter']}-{yr}",
                    "title": f"AEAT: Presentar Modelo 111 Q{q['quarter']}",
                    "start_time": q["deadline_111_115"],
                    "end_time": q["deadline_111_115"],
                    "description": f"Retenciones a cuenta de IRPF practicadas sobre trabajadores o profesionales durante el Q{q['quarter']} de {yr}.",
                    "location": "Sede Electrónica AEAT",
                    "attendees": None
                })
                deadlines.append({
                    "id": f"fiscal-115-q{q['quarter']}-{yr}",
                    "title": f"AEAT: Presentar Modelo 115 Q{q['quarter']}",
                    "start_time": q["deadline_111_115"],
                    "end_time": q["deadline_111_115"],
                    "description": f"Retenciones practicadas sobre alquileres de locales urbanos correspondientes al Q{q['quarter']} de {yr}.",
                    "location": "Sede Electrónica AEAT",
                    "attendees": None
                })

            # Anuales
            deadlines.append({
                "id": f"fiscal-390-annual-{yr}",
                "title": f"AEAT: Presentar Modelo 390 (IVA Anual)",
                "start_time": f"{yr+1}-01-30 23:59",
                "end_time": f"{yr+1}-01-30 23:59",
                "description": f"Declaración resumen anual del IVA correspondiente a todo el ejercicio {yr}.",
                "location": "Sede Electrónica AEAT",
                "attendees": None
            })
            deadlines.append({
                "id": f"fiscal-190-annual-{yr}",
                "title": f"AEAT: Presentar Modelo 190 (Anual Retenciones)",
                "start_time": f"{yr+1}-01-30 23:59",
                "end_time": f"{yr+1}-01-30 23:59",
                "description": f"Resumen anual del Modelo 111 correspondiente al ejercicio {yr}.",
                "location": "Sede Electrónica AEAT",
                "attendees": None
            })
            deadlines.append({
                "id": f"fiscal-180-annual-{yr}",
                "title": f"AEAT: Presentar Modelo 180 (Anual Alquileres)",
                "start_time": f"{yr+1}-01-30 23:59",
                "end_time": f"{yr+1}-01-30 23:59",
                "description": f"Resumen anual del Modelo 115 correspondiente al ejercicio {yr}.",
                "location": "Sede Electrónica AEAT",
                "attendees": None
            })

            # Campaña Renta
            deadlines.append({
                "id": f"fiscal-100-income-{yr}",
                "title": f"AEAT: Campaña de la Renta (Modelo 100)",
                "start_time": f"{yr+1}-04-06 09:00",
                "end_time": f"{yr+1}-06-30 23:59",
                "description": f"Campaña de la declaración del Impuesto sobre la Renta de las Personas Físicas (IRPF) del ejercicio {yr}.",
                "location": "Sede Electrónica AEAT",
                "attendees": None
            })

        # Filtrar por rango
        filtered = []
        for d in deadlines:
            d_date = d["start_time"][:10]
            if start_date and end_date:
                if start_date <= d_date <= end_date:
                    filtered.append(d)
            elif start_date:
                if d_date >= start_date:
                    filtered.append(d)
            elif end_date:
                if d_date <= end_date:
                    filtered.append(d)
            else:
                filtered.append(d)

        return filtered

    def calculate_model_303_from_data(
        self,
        fiscal_year: int,
        quarter: int,
        sales: list,
        purchases: list,
        prorrata_pct: float = 100.0,
        compensacion_periodos_anteriores: float = 0.0
    ):
        """
        Calcula las casillas oficiales del Modelo 303 de la AEAT según desglose impositivo y regla de prorrata.
        Conforme a la Orden EHA/3786/2008 y Orden HFP/1395/2023.
        """
        from app.domain.models.billing import Model303ResultDTO
        
        base_21 = sum(s.get("base", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 21.0) < 0.1)
        cuota_21 = sum(s.get("tax", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 21.0) < 0.1)

        base_10 = sum(s.get("base", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 10.0) < 0.1)
        cuota_10 = sum(s.get("tax", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 10.0) < 0.1)

        base_4 = sum(s.get("base", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 4.0) < 0.1)
        cuota_4 = sum(s.get("tax", 0.0) for s in sales if abs(s.get("vat_rate", 0.0) - 4.0) < 0.1)
        
        total_devengada = round(cuota_21 + cuota_10 + cuota_4, 2)
        
        base_deducible_corriente = sum(p.get("base", 0.0) for p in purchases if not p.get("is_investment", False))
        cuota_deducible_corriente = sum(p.get("tax", 0.0) for p in purchases if not p.get("is_investment", False))
        
        base_deducible_inversion = sum(p.get("base", 0.0) for p in purchases if p.get("is_investment", False))
        cuota_deducible_inversion = sum(p.get("tax", 0.0) for p in purchases if p.get("is_investment", False))
        
        # Aplicación de la regla de prorrata (general)
        factor_prorrata = max(0.0, min(100.0, prorrata_pct)) / 100.0
        total_deducible = round((cuota_deducible_corriente + cuota_deducible_inversion) * factor_prorrata, 2)
        resultado_regimen_general = round(total_devengada - total_deducible, 2)
        resultado_autoliquidacion = round(resultado_regimen_general - compensacion_periodos_anteriores, 2)
        
        casillas = {
            "01": round(base_4, 2), "02": 4.0, "03": round(cuota_4, 2),
            "04": round(base_10, 2), "05": 10.0, "06": round(cuota_10, 2),
            "07": round(base_21, 2), "08": 21.0, "09": round(cuota_21, 2),
            "27": total_devengada,
            "28": round(base_deducible_corriente, 2),
            "29": round(cuota_deducible_corriente, 2),
            "30": round(base_deducible_inversion, 2),
            "31": round(cuota_deducible_inversion, 2),
            "37": total_deducible,
            "46": resultado_regimen_general,
            "110": round(compensacion_periodos_anteriores, 2),
            "71": resultado_autoliquidacion
        }
        
        return Model303ResultDTO(
            fiscal_year=fiscal_year,
            quarter=quarter,
            base_general_21=round(base_21, 2),
            tipo_general_21=21.0,
            cuota_general_21=round(cuota_21, 2),
            base_reducido_10=round(base_10, 2),
            tipo_reducido_10=10.0,
            cuota_reducido_10=round(cuota_10, 2),
            base_superreducido_4=round(base_4, 2),
            tipo_superreducido_4=4.0,
            cuota_superreducido_4=round(cuota_4, 2),
            total_cuota_devengada=total_devengada,
            base_deducible_corriente=round(base_deducible_corriente, 2),
            iva_deducible_corriente=round(cuota_deducible_corriente, 2),
            base_deducible_inversion=round(base_deducible_inversion, 2),
            iva_deducible_inversion=round(cuota_deducible_inversion, 2),
            prorrata_pct=prorrata_pct,
            total_iva_deducible=total_deducible,
            resultado_regimen_general=resultado_regimen_general,
            casilla_110_compensacion_anterior=round(compensacion_periodos_anteriores, 2),
            resultado_autoliquidacion=resultado_autoliquidacion,
            casillas=casillas
        )

    def calculate_model_130_from_data(
        self,
        fiscal_year: int,
        quarter: int,
        accumulated_incomes: float,
        accumulated_expenses: float,
        previous_payments: float = 0.0,
        retentions_supported: float = 0.0,
        deduction_art_80_bis: float = 0.0
    ):
        """
        Calcula la autoliquidación del pago fraccionado de IRPF (Modelo 130) acumulativa anual (art. 109 RIRPF).
        """
        from app.domain.models.billing import Model130ResultDTO
        
        rendimiento_neto = round(accumulated_incomes - accumulated_expenses, 2)
        # 20% sobre rendimiento neto positivo
        pago_fraccionado = round(max(0.0, rendimiento_neto * 0.20), 2)
        resultado = round(max(0.0, pago_fraccionado - previous_payments - retentions_supported - deduction_art_80_bis), 2)
        
        casillas = {
            "01": round(accumulated_incomes, 2),
            "02": round(accumulated_expenses, 2),
            "03": rendimiento_neto,
            "04": pago_fraccionado,
            "07": round(previous_payments, 2),
            "08": round(retentions_supported, 2),
            "13": round(deduction_art_80_bis, 2),
            "19": resultado
        }
        
        return Model130ResultDTO(
            fiscal_year=fiscal_year,
            quarter=quarter,
            casilla_01_ingresos_acumulados=round(accumulated_incomes, 2),
            casilla_02_gastos_acumulados=round(accumulated_expenses, 2),
            casilla_03_rendimiento_neto=rendimiento_neto,
            casilla_04_pago_fraccionado_previo=pago_fraccionado,
            casilla_07_pagos_anteriores=round(previous_payments, 2),
            casilla_08_retenciones_soportadas=round(retentions_supported, 2),
            casilla_13_deduccion=round(deduction_art_80_bis, 2),
            casilla_19_resultado_ingresar=resultado,
            casillas=casillas
        )

    def calculate_model_111_from_data(
        self,
        fiscal_year: int,
        quarter: int,
        work_withholdings: list = None,
        prof_withholdings: list = None
    ):
        """Calcula retenciones del trabajo y profesionales para el Modelo 111 de la AEAT."""
        from app.domain.models.billing import Model111ResultDTO

        work = work_withholdings or []
        prof = prof_withholdings or []

        num_trabajo = len(work)
        base_trabajo = round(sum(w.get("base", 0.0) for w in work), 2)
        ret_trabajo = round(sum(w.get("amount", 0.0) for w in work), 2)

        num_prof = len(prof)
        base_prof = round(sum(w.get("base", 0.0) for w in prof), 2)
        ret_prof = round(sum(w.get("amount", 0.0) for w in prof), 2)

        total_ingresar = round(ret_trabajo + ret_prof, 2)

        casillas = {
            "01": num_trabajo,
            "02": base_trabajo,
            "03": ret_trabajo,
            "07": num_prof,
            "08": base_prof,
            "09": ret_prof,
            "28": total_ingresar
        }

        return Model111ResultDTO(
            fiscal_year=fiscal_year,
            quarter=quarter,
            perceptores_trabajo=num_trabajo,
            base_trabajo=base_trabajo,
            retenciones_trabajo=ret_trabajo,
            perceptores_profesionales=num_prof,
            base_profesionales=base_prof,
            retenciones_profesionales=ret_prof,
            resultado_total=total_ingresar,
            casillas=casillas
        )

    def calculate_model_115_from_data(
        self,
        fiscal_year: int,
        quarter: int,
        rental_withholdings: list = None
    ):
        """Calcula retenciones sobre arrendamientos urbanos para el Modelo 115 de la AEAT (19%)."""
        from app.domain.models.billing import Model115ResultDTO

        rentals = rental_withholdings or []
        num_arrendadores = len(rentals)
        base_rentals = round(sum(r.get("base", 0.0) for r in rentals), 2)
        ret_rentals = round(sum(r.get("amount", 0.0) for r in rentals), 2)

        casillas = {
            "01": num_arrendadores,
            "02": base_rentals,
            "03": ret_rentals,
            "05": ret_rentals
        }

        return Model115ResultDTO(
            fiscal_year=fiscal_year,
            quarter=quarter,
            numero_arrendadores=num_arrendadores,
            base_arrendamientos=base_rentals,
            retenciones_arrendamientos=ret_rentals,
            resultado_a_ingresar=ret_rentals,
            casillas=casillas
        )

    def calculate_model_111(self, fiscal_year: int, quarter: int, withholdings: list) -> dict:
        """Calcula retenciones para el Modelo 111 (compatibilidad retroactiva)."""
        total_perceptores = len(withholdings)
        total_bases = round(sum(w.get("base", 0.0) for w in withholdings), 2)
        total_retenciones = round(sum(w.get("amount", 0.0) for w in withholdings), 2)
        return {
            "fiscal_year": fiscal_year,
            "quarter": quarter,
            "total_perceptores": total_perceptores,
            "total_bases": total_bases,
            "total_retenciones": total_retenciones
        }

    def calculate_model_115(self, fiscal_year: int, quarter: int, withholdings: list) -> dict:
        """Calcula retenciones para el Modelo 115 (compatibilidad retroactiva)."""
        total_arrendadores = len(withholdings)
        total_bases = round(sum(w.get("base", 0.0) for w in withholdings), 2)
        total_retenciones = round(sum(w.get("amount", 0.0) for w in withholdings), 2)
        return {
            "fiscal_year": fiscal_year,
            "quarter": quarter,
            "total_arrendadores": total_arrendadores,
            "total_bases": total_bases,
            "total_retenciones": total_retenciones
        }

