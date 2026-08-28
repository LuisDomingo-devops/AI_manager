from typing import Protocol, Dict, Any

class DocumentCustomizationPort(Protocol):
    def get_customization(self, client_id: str) -> Dict[str, Any]:
        """Recupera la personalización de documentos para un inquilino."""
        ...

    def save_customization(self, client_id: str, data: Dict[str, Any]) -> None:
        """Guarda o actualiza la personalización de documentos para un inquilino."""
        ...
