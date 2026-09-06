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

    def get_rules(self) -> Dict[str, Any]:
        """Carga las reglas fiscales desde el archivo JSON."""
        try:
            if self._rules_path.exists():
                with open(self._rules_path, "r", encoding="utf-8") as f:
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

    def save_rules(self, rules: Dict[str, Any]) -> None:
        """Persiste las reglas fiscales actualizadas en el archivo JSON."""
        try:
            self._rules_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._rules_path, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            app_logger.error(f"Error al escribir tax_rules.json: {str(e)}")
            raise e
