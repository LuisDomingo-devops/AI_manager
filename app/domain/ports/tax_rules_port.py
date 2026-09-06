from abc import ABC, abstractmethod
from typing import Dict, Any

class TaxRulesPort(ABC):
    @abstractmethod
    def get_rules(self) -> Dict[str, Any]:
        """Recupera las reglas fiscales actuales."""
        pass

    @abstractmethod
    def save_rules(self, rules: Dict[str, Any]) -> None:
        """Persiste las reglas fiscales actualizadas."""
        pass
