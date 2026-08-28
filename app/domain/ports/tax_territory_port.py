from typing import Protocol, List, Dict, Any

class TaxTerritoryPort(Protocol):
    def get_name(self) -> str:
        """Retorna el nombre descriptivo de la región fiscal."""
        ...

    def get_supported_iva_rates(self) -> List[float]:
        """Retorna la lista de tipos impositivos de IVA/IGIC aplicables en la región."""
        ...

    def get_default_iva_rate(self) -> float:
        """Retorna la tasa de IVA/IGIC por defecto de la región."""
        ...

    def calculate_tax_dues(self, income_base: float, expense_base: float) -> Dict[str, Any]:
        """Calcula el balance impositivo básico según la legislación local."""
        ...
