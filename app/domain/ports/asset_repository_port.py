from typing import Protocol, List, Dict, Any, Optional

class AssetRepositoryPort(Protocol):
    def save_asset(self, client_id: str, asset_data: Dict[str, Any]) -> int:
        """Guarda o actualiza un bien de inversión en la base de datos y retorna su ID."""
        ...

    def get_asset(self, client_id: str, asset_id: int) -> Optional[Dict[str, Any]]:
        """Recupera un bien de inversión específico por su ID."""
        ...

    def list_assets(self, client_id: str) -> List[Dict[str, Any]]:
        """Lista todos los bienes de inversión de un inquilino."""
        ...
