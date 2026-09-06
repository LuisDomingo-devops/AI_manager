from typing import List, Dict, Any
from app.domain.ports.tax_territory_port import TaxTerritoryPort

class CommonTerritoryAdapter(TaxTerritoryPort):
    def get_name(self) -> str:
        return "Régimen Fiscal Común (AEAT - Península y Baleares)"

    def get_supported_iva_rates(self) -> List[float]:
        return [21.0, 10.0, 4.0, 0.0]

    def get_default_iva_rate(self) -> float:
        try:
            from app.domain.services.tax_engine import TaxEngine
            from app.infrastructure.adapters.file_tax_rules_adapter import FileTaxRulesAdapter
            engine = TaxEngine(tax_rules_port=FileTaxRulesAdapter())
            rules = engine.load_rules()
            return rules.get("iva_general_rate", 21.0)
        except Exception:
            return 21.0

    def calculate_tax_dues(self, income_base: float, expense_base: float) -> Dict[str, Any]:
        iva_devengado = income_base * 0.21
        iva_deducible = expense_base * 0.21
        resultado = iva_devengado - iva_deducible
        return {
            "territory": "comun",
            "iva_devengado": round(iva_devengado, 2),
            "iva_deducible": round(iva_deducible, 2),
            "resultado_iva": round(resultado, 2)
        }
