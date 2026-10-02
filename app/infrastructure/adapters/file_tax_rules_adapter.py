import json
from pathlib import Path
from typing import Dict, Any
from app.domain.ports.tax_rules_port import TaxRulesPort
from app.utils.logger import app_logger

class FileTaxRulesAdapter(TaxRulesPort):
    def __init__(self, file_path: str = None):
        if file_path:
            self._rules_path = Path(file_path)
        else:
            # Default to app/data/tax_rules.json
            self._rules_path = Path(__file__).resolve().parent.parent.parent / "data" / "tax_rules.json"

    def get_rules(self, date: str = None) -> Dict[str, Any]:
        """Carga las reglas fiscales aplicables a la fecha desde el archivo JSON."""
        data = None
        try:
            if self._rules_path.exists():
                with open(self._rules_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
        except Exception as e:
            app_logger.error(f"Error al cargar tax_rules.json: {str(e)}")

        if data and "versions" in data:
            if not date:
                # Si no hay fecha, buscar la versión vigente (valid_until = null) o la última
                for v in reversed(data["versions"]):
                    if v.get("valid_until") is None:
                        return v["rules"]
                return data["versions"][-1]["rules"] if data["versions"] else {}
            else:
                # Buscar la versión que aplique a la fecha
                for v in data["versions"]:
                    valid_from = v.get("valid_from", "0000-00-00")
                    valid_until = v.get("valid_until")
                    if valid_from <= date:
                        if valid_until is None or date <= valid_until:
                            return v["rules"]
                return data["versions"][-1]["rules"] if data["versions"] else {}
        
        # Fallbacks por defecto si no se puede leer o no tiene el formato correcto
        return {
            "iva_general_rate": 21.0,
            "irpf_profesionales_rate": 15.0,
            "last_updated": "2026-10-02",
            "boe_reference": "Default Seed Fallback - Orden ESS/2098/2014 & RD 439/2007",
            "payroll": {
                "worker_cc_rate": 4.70,
                "worker_unemployment_rate": 1.55,
                "worker_unemployment_temp": 1.60,
                "worker_fp_rate": 0.10,
                "worker_mei_rate": 0.12,
                "employer_cc_rate": 23.60,
                "employer_unemployment_rate": 5.50,
                "employer_unemployment_temp": 6.70,
                "employer_fogasa_rate": 0.20,
                "employer_fp_rate": 0.60,
                "employer_mei_rate": 0.58,
                "employer_atep_rate": 1.50,
                "max_monthly_base_cap": 4720.50,
                "min_monthly_bases": {
                    "1": 1847.40,
                    "2": 1532.10,
                    "3": 1332.90,
                    "4": 1323.00,
                    "5": 1323.00,
                    "6": 1323.00,
                    "7": 1323.00,
                    "8": 1323.00,
                    "9": 1323.00,
                    "10": 1323.00,
                    "11": 1323.00
                },
                "irpf_brackets": [
                    { "limit": 12450.00, "rate": 19.00 },
                    { "limit": 20200.00, "rate": 24.00 },
                    { "limit": 35200.00, "rate": 30.00 },
                    { "limit": 60000.00, "rate": 37.00 },
                    { "limit": 300000.00, "rate": 45.00 },
                    { "limit": None, "rate": 47.00 }
                ],
                "irpf_minimums": {
                    "taxpayer_general": 5550.00,
                    "descendant_1": 2400.00,
                    "descendant_2": 2700.00,
                    "descendant_3": 4000.00,
                    "descendant_4_plus": 4500.00,
                    "descendant_under_3_bonus": 2800.00
                },
                "art_81_limits": {
                    "situation_1": { "0": 15876.00, "1": 17260.00, "2_plus": 18640.00 },
                    "situation_2": { "0": 17107.00, "1": 18130.00, "2_plus": 19260.00 },
                    "situation_3": { "0": 15876.00, "1": 16340.00, "2_plus": 16860.00 }
                }
            }
        }

    def save_rules(self, rules: Dict[str, Any]) -> None:
        """Persiste las reglas fiscales actualizadas añadiendo una nueva versión."""
        from datetime import datetime
        try:
            data = {"versions": []}
            if self._rules_path.exists():
                with open(self._rules_path, "r", encoding="utf-8") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        pass
            
            if "versions" not in data:
                data = {"versions": []}
            
            now_str = datetime.now().strftime("%Y-%m-%d")
            
            # Cerrar la versión anterior si la hay
            if data["versions"]:
                last_version = data["versions"][-1]
                if last_version.get("valid_until") is None:
                    last_version["valid_until"] = now_str
                    
            # Añadir nueva versión
            new_version = {
                "valid_from": now_str,
                "valid_until": None,
                "rules": rules
            }
            data["versions"].append(new_version)

            self._rules_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._rules_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app_logger.error(f"Error al escribir tax_rules.json: {str(e)}")
            raise e
