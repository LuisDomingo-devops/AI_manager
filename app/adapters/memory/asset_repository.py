from typing import List, Dict, Any, Optional
from app.domain.ports.asset_repository_port import AssetRepositoryPort
from app.infrastructure.database.memory.memory import _get_connection

class MemoryAssetRepository(AssetRepositoryPort):
    def save_asset(self, client_id: str, asset_data: Dict[str, Any]) -> int:
        name = asset_data["name"]
        purchase_date = asset_data["purchase_date"]
        cost = float(asset_data["cost"])
        salvage_value = float(asset_data.get("salvage_value", 0.0))
        useful_life_years = int(asset_data["useful_life_years"])
        
        asset_id = asset_data.get("id")
        
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            if asset_id:
                cursor.execute("""
                    UPDATE assets 
                    SET name = ?, purchase_date = ?, cost = ?, salvage_value = ?, useful_life_years = ?
                    WHERE id = ? AND client_id = ?
                """, (name, purchase_date, cost, salvage_value, useful_life_years, asset_id, client_id))
                conn.commit()
                return asset_id
            else:
                cursor.execute("""
                    INSERT INTO assets (client_id, name, purchase_date, cost, salvage_value, useful_life_years)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (client_id, name, purchase_date, cost, salvage_value, useful_life_years))
                conn.commit()
                return cursor.lastrowid

    def get_asset(self, client_id: str, asset_id: int) -> Optional[Dict[str, Any]]:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assets WHERE id = ? AND client_id = ?", (asset_id, client_id))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def list_assets(self, client_id: str) -> List[Dict[str, Any]]:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM assets WHERE client_id = ? ORDER BY purchase_date ASC", (client_id,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
