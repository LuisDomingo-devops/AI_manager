from typing import List, Dict, Any
from app.domain.ports.tax_territory_port import TaxTerritoryPort

class CanariasTerritoryAdapter(TaxTerritoryPort):
    def get_name(self) -> str:
        return "Régimen Fiscal de Canarias (IGIC)"

    def get_supported_iva_rates(self) -> List[float]:
        return [7.0, 3.0, 0.0, 9.5, 15.0, 20.0]

    def get_default_iva_rate(self) -> float:
        return 7.0

    def calculate_tax_dues(self, income_base: float, expense_base: float) -> Dict[str, Any]:
        igic_devengado = income_base * 0.07
        igic_deducible = expense_base * 0.07
        resultado = igic_devengado - igic_deducible
        return {
            "territory": "canarias",
            "igic_devengado": round(igic_devengado, 2),
            "igic_deducible": round(igic_deducible, 2),
            "resultado_igic": round(resultado, 2)
        }
