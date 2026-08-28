import re
from typing import Dict, Any, Tuple
from app.domain.ports.document_customization_port import DocumentCustomizationPort

class DocumentCustomizationService:
    def __init__(self, adapter: DocumentCustomizationPort):
        self.adapter = adapter

    def get_customization(self, client_id: str) -> Dict[str, Any]:
        """Recupera la personalización de documentos para el inquilino."""
        return self.adapter.get_customization(client_id)

    def save_customization(self, client_id: str, data: Dict[str, Any]) -> None:
        """Valida y guarda la personalización de documentos para el inquilino."""
        for field in ("primary_color", "secondary_color"):
            val = data.get(field)
            if val and not re.match(r"^#[0-9A-Fa-f]{6}$", val):
                raise ValueError(f"El campo {field} debe ser un color hexadecimal válido (ej: #1E293B)")
        self.adapter.save_customization(client_id, data)

    @staticmethod
    def hex_to_rgb(hex_str: str, default: Tuple[float, float, float] = (0.12, 0.23, 0.35)) -> Tuple[float, float, float]:
        """Convierte una cadena hexadecimal (ej: #1E293B) a una tupla RGB normalizada (0.0 a 1.0) para ReportLab."""
        if not hex_str:
            return default
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            try:
                r = int(hex_str[0:2], 16) / 255.0
                g = int(hex_str[2:4], 16) / 255.0
                b = int(hex_str[4:6], 16) / 255.0
                return r, g, b
            except ValueError:
                pass
        return default
