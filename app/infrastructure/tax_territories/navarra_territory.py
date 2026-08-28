from typing import List, Dict, Any
from app.domain.ports.tax_territory_port import TaxTerritoryPort

class NavarraTerritoryAdapter(TaxTerritoryPort):
    def get_name(self) -> str:
        return "Hacienda Foral de Navarra"

    def get_supported_iva_rates(self) -> List[float]:
        # Navarra comparte los tipos del régimen común
        return [21.0, 10.0, 4.0, 0.0]

    def get_default_iva_rate(self) -> float:
        return 21.0

    def calculate_tax_dues(self, income_base: float, expense_base: float) -> Dict[str, Any]:
        iva_devengado = income_base * 0.21
        iva_deducible = expense_base * 0.21
        resultado = iva_devengado - iva_deducible
        return {
            "territory": "navarra",
            "iva_devengado": round(iva_devengado, 2),
            "iva_deducible": round(iva_deducible, 2),
            "resultado_iva": round(resultado, 2)
        }
