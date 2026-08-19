import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Tuple, Dict, Any
from app.utils.logger import app_logger

# Expresiones regulares para NIF español (A1234567B, 12345678Z, etc.)
NIF_REGEX = re.compile(r'\b[A-HJ-NP-SUVWXY\d]\d{7}[A-Z\d]\b', re.IGNORECASE)

# Expresiones regulares para fechas comunes
DATE_REGEX = re.compile(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b')
DATE_ISO_REGEX = re.compile(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b')

# Expresiones regulares para importes
MONEY_REGEX = re.compile(r'\b\d+(?:[.,]\d{2})?\b')

class TaxEngine:
    _rules_path = Path(__file__).resolve().parent / "tax_rules.json"

    @classmethod
    def load_rules(cls) -> Dict[str, Any]:
        """Carga las reglas fiscales desde el archivo JSON."""
        try:
            if cls._rules_path.exists():
                with open(cls._rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            app_logger.error(f"Error al cargar tax_rules.json: {str(e)}")
        
        # Fallbacks por defecto si no se puede leer
        return {
            "iva_general_rate": 21.0,
            "irpf_profesionales_rate": 15.0,
            "last_updated": "2026-08-13",
            "boe_reference": "Default Seed Fallback"
        }

    @classmethod
    def update_tax_rules(cls, new_rules: Dict[str, Any], boe_link: str, boe_section: str, confirmed_by_user: bool = False) -> Dict[str, Any]:
        """
        Actualiza las reglas fiscales en tax_rules.json tras confirmación humana.
        """
        # Validar enlace obligatorio del BOE y sección
        if not boe_link or not boe_link.startswith("http"):
            return {"status": "error", "message": "Es obligatorio proporcionar un enlace web directo y válido al documento del BOE."}
        if not boe_section or len(boe_section.strip()) < 3:
            return {"status": "error", "message": "Es obligatorio citar el artículo, sección o página específica del BOE que respalda la norma."}

        current_rules = cls.load_rules()
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

        # Guardar en disco
        try:
            proposed["last_updated"] = datetime.now().strftime("%Y-%m-%d")
            proposed["boe_reference"] = f"{boe_link} ({boe_section})"
            with open(cls._rules_path, "w", encoding="utf-8") as f:
                json.dump(proposed, f, indent=2, ensure_ascii=False)
            return {
                "status": "ok",
                "message": f"Reglas fiscales actualizadas exitosamente con los cambios: {', '.join(changes)}. Referencia del BOE guardada.",
                "rules": proposed
            }
        except Exception as e:
            app_logger.error(f"Error al escribir tax_rules.json: {str(e)}")
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
    def resolve_rates_with_confidence(cls, text: str) -> Dict[str, Any]:
        """
        Busca tasas de IVA e IRPF y evalúa la confianza de la extracción.
        No asume un tipo de IVA al 21% por defecto si no está explícito en el documento,
        marcando requires_manual_confirmation para evitar sanciones del art. 191 LGT por deducciones indebidas.
        """
        text_lower = text.lower()
        iva_rate = None
        is_iva_inferred = False
        confidence = 1.0

        iva_rate_match = re.search(r'(?:iva|i\.v\.a\.)[^0-9%]*?(\d+(?:[.,]\d+)?)\s*%', text_lower)
        if iva_rate_match:
            try:
                iva_rate = float(iva_rate_match.group(1).replace(",", "."))
            except Exception:
                iva_rate = 21.0
        else:
            # Buscar menciones de exención o régimen especial
            if any(term in text_lower for term in ["exento", "exenta", "art. 20", "artículo 20", "inversión del sujeto pasivo", "0%"]):
                iva_rate = 0.0
            else:
                rules = cls.load_rules()
                iva_rate = rules.get("iva_general_rate", 21.0)
                is_iva_inferred = True
                confidence = 0.60

        irpf_rate = 0.0
        irpf_rate_match = re.search(r'(?:irpf|i\.r\.p\.f\.|retenci[oó]n)[^0-9%-]*?(-?\d+(?:[.,]\d+)?)\s*%', text_lower)
        if irpf_rate_match:
            try:
                irpf_rate = abs(float(irpf_rate_match.group(1).replace(",", ".")))
            except Exception:
                irpf_rate = 0.0

        return {
            "iva_rate": iva_rate,
            "irpf_rate": irpf_rate,
            "is_iva_inferred": is_iva_inferred,
            "confidence_score": confidence,
            "requires_manual_confirmation": is_iva_inferred
        }

    @classmethod
    def resolve_rates(cls, text: str) -> Tuple[float, float]:
        """
        Busca tasas de IVA e IRPF delegando en resolve_rates_with_confidence.
        """
        res = cls.resolve_rates_with_confidence(text)
        return res["iva_rate"], res["irpf_rate"]

    @classmethod
    def extract_financials(cls, text: str, text_lower: str, iva_rate: float, irpf_rate: float) -> Tuple[float, float, float, float]:
        """
        Extrae base_imponible, iva_amount, irpf_amount y total_amount del texto de forma estructurada.
        """
        base_imponible = 0.0
        total_amount = 0.0

        # Buscar total de forma prioritaria
        total_matches = re.findall(r'(?:total|importe total|a pagar|total factura)\s*(?:[a-z\s]+)?[\s:]*([0-9.,\s]+(?:€|\b))', text_lower)
        if total_matches:
            for m in reversed(total_matches):
                val = cls.parse_number(m)
                if val > 0:
                    total_amount = val
                    break

        # Buscar base imponible
        base_matches = re.findall(r'(?:base imponible|subtotal|base|neto)[\s:]*([0-9.,\s]+(?:€|\b))', text_lower)
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
        # Buscar importe explícito de retención IRPF si existe
        explicit_irpf = 0.0
        irpf_amt_matches = re.findall(r'(?:retenci[oó]n(?:[\s\w%()]+)?|irpf(?:[\s\w%()]+)?)[\s:]*[-]?([0-9.,]+)\s*(?:€|eur|\b)', text_lower)
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
