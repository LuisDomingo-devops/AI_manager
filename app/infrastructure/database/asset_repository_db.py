import sqlite3
from typing import List, Dict, Any, Optional
from app.domain.ports.asset_repository_port import AssetRepositoryPort
from app.adapters.memory.memory import _get_connection

class SqliteAssetRepositoryAdapter(AssetRepositoryPort):
    def save_asset(self, client_id: str, asset_data: Dict[str, Any]) -> int:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            asset_id = asset_data.get("id")
            
            if asset_id:
                cursor.execute(
                    """
                    UPDATE assets 
                    SET name = ?, purchase_date = ?, cost = ?, useful_life_years = ?, 
                        depreciation_method = ?, salvage_value = ?, category = ?, updated_at = datetime('now')
                    WHERE id = ? AND client_id = ?
                    """,
                    (
                        asset_data["name"],
                        asset_data["purchase_date"],
                        asset_data["cost"],
                        asset_data["useful_life_years"],
                        asset_data.get("depreciation_method", "lineal"),
                        asset_data.get("salvage_value", 0.0),
                        asset_data.get("category"),
                        asset_id,
                        client_id
                    )
                )
                ret_id = asset_id
            else:
                cursor.execute(
                    """
                    INSERT INTO assets (
                        client_id, name, purchase_date, cost, useful_life_years, 
                        depreciation_method, salvage_value, category, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        client_id,
                        asset_data["name"],
                        asset_data["purchase_date"],
                        asset_data["cost"],
                        asset_data["useful_life_years"],
                        asset_data.get("depreciation_method", "lineal"),
                        asset_data.get("salvage_value", 0.0),
                        asset_data.get("category")
                    )
                )
                ret_id = cursor.lastrowid
            
            conn.commit()
            return ret_id

    def get_asset(self, client_id: str, asset_id: int) -> Optional[Dict[str, Any]]:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, client_id, name, purchase_date, cost, useful_life_years, 
                       depreciation_method, salvage_value, category, created_at, updated_at
                FROM assets 
                WHERE id = ? AND client_id = ?
                """,
                (asset_id, client_id)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def list_assets(self, client_id: str) -> List[Dict[str, Any]]:
        with _get_connection(client_id) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, client_id, name, purchase_date, cost, useful_life_years, 
                       depreciation_method, salvage_value, category, created_at, updated_at
                FROM assets 
                WHERE client_id = ?
                ORDER BY id ASC
                """,
                (client_id,)
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
