from abc import ABC, abstractmethod
from typing import Dict, Any

class TaxRulesPort(ABC):
    @abstractmethod
    def get_rules(self, date: str = None) -> Dict[str, Any]:
        """Recupera las reglas fiscales aplicables a una fecha dada, o las actuales si no se provee fecha."""
        pass

    @abstractmethod
    def save_rules(self, rules: Dict[str, Any]) -> None:
        """Persiste las reglas fiscales actualizadas."""
        pass
