import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.domain.services.depreciation_service import DepreciationService
from app.infrastructure.database.asset_repository_db import SqliteAssetRepositoryAdapter
from app.tools.server.aeat_automation_tools import (
    register_asset_tool,
    generate_depreciation_proposal_tool
)
from app.adapters.memory.memory import _get_connection


class MockAssetRepository:
    def __init__(self, assets):
        self.assets = assets

    def list_assets(self, client_id):
        return self.assets


def test_depreciation_lineal_year_standard():
    # Activo comprado antes del año, amortización completa estándar
    mock_assets = [{
        "id": 1,
        "name": "Servidor Linux",
        "purchase_date": "2024-01-15",
        "cost": 1000.0,
        "useful_life_years": 5,
        "salvage_value": 0.0,
        "depreciation_method": "lineal"
    }]
    repo = MockAssetRepository(mock_assets)
    service = DepreciationService(repo)
    
    proposal = service.calculate_depreciation_proposal("default", 2025)
    assert len(proposal) == 1
    assert proposal[0]["amount"] == 200.0  # 1000 / 5


def test_depreciation_lineal_prorrata():
    # Comprado el 1 de julio del año evaluado, prorrata de 6 meses (de julio a diciembre)
    mock_assets = [{
        "id": 2,
        "name": "MacBook Pro",
        "purchase_date": "2025-07-01",
        "cost": 2400.0,
        "useful_life_years": 4,
        "salvage_value": 0.0,
        "depreciation_method": "lineal"
    }]
    repo = MockAssetRepository(mock_assets)
    service = DepreciationService(repo)
    
    proposal = service.calculate_depreciation_proposal("default", 2025)
    assert len(proposal) == 1
    # cuota anual: 2400 / 4 = 600. Prorrata 6 meses: 600 * (6/12) = 300.0
    assert proposal[0]["amount"] == 300.0


def test_depreciation_lineal_last_year_prorrata():
    # Comprado el 1 de julio del año 2024 con vida útil de 2 años
    # Amortiza en 2024: 6 meses (julio a diciembre) -> 250 €
    # Amortiza en 2025: 12 meses -> 500 €
    # Amortiza en 2026 (último año): 6 meses restantes (enero a junio) -> 250 €
    mock_assets = [{
        "id": 3,
        "name": "Mobiliario Oficina",
        "purchase_date": "2024-07-01",
        "cost": 1000.0,
        "useful_life_years": 2,
        "salvage_value": 0.0,
        "depreciation_method": "lineal"
    }]
    repo = MockAssetRepository(mock_assets)
    service = DepreciationService(repo)
    
    proposal = service.calculate_depreciation_proposal("default", 2026)
    assert len(proposal) == 1
    assert proposal[0]["amount"] == 250.0  # 500 * (6/12)


def test_depreciation_fully_depreciated():
    # Activo ya amortizado por completo
    mock_assets = [{
        "id": 4,
        "name": "Scanner",
        "purchase_date": "2020-01-01",
        "cost": 500.0,
        "useful_life_years": 3,
        "salvage_value": 0.0,
        "depreciation_method": "lineal"
    }]
    repo = MockAssetRepository(mock_assets)
    service = DepreciationService(repo)
    
    proposal = service.calculate_depreciation_proposal("default", 2025)
    # Se adquirió en 2020 con 3 años de vida útil (2020, 2021, 2022). En 2025 ya venció.
    assert len(proposal) == 0


@pytest.mark.asyncio
async def test_sqlite_asset_repository_and_tools():
    from app.infrastructure.database.memory.memory import tenant_context
    tenant_context.set("default")
    # Ejecutar migración de assets
    with _get_connection("default") as conn:
        conn.execute("DROP TABLE IF EXISTS assets")
        # Re-inicializar a través de la migración
        import importlib
        mod_mig = importlib.import_module("migrations.versions.007_asset_depreciation")
        upgrade = mod_mig.upgrade
        upgrade(conn)

    # 1. Probar registro de activo mediante la herramienta register_asset_tool
    res_reg = await register_asset_tool(
        name="Aire Acondicionado",
        purchase_date="2026-05-10",
        cost=1200.0,
        useful_life_years=10,
        salvage_value=200.0
    )
    assert res_reg["status"] == "ok"
    asset_id = res_reg["asset_id"]
    
    # 2. Leer desde el adaptador para validar persistencia
    adapter = SqliteAssetRepositoryAdapter()
    asset = adapter.get_asset("default", asset_id)
    assert asset is not None
    assert asset["name"] == "Aire Acondicionado"
    assert asset["cost"] == 1200.0

    # 3. Listar activos
    all_assets = adapter.list_assets("default")
    assert len(all_assets) >= 1

    # 4. Probar propuesta de amortización sin confirmación (confirmed_by_user=False)
    res_proposal = await generate_depreciation_proposal_tool(2026, confirmed_by_user=False)
    assert res_proposal["status"] == "pending_confirmation"
    assert len(res_proposal["proposal"]) == 1
    # Cuota anual: (1200 - 200) / 10 = 100. Prorrata 8 meses de uso (mayo a diciembre): 100 * (8/12) = 66.67
    assert res_proposal["proposal"][0]["amount"] == 66.67

    # 5. Probar propuesta con confirmación (confirmed_by_user=True)
    # Creamos tabla journal/ledger de prueba si no existe
    with _get_connection("default") as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS journal_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                concept TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ledger_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                journal_entry_id INTEGER NOT NULL,
                account_code TEXT NOT NULL,
                debe TEXT NOT NULL,
                haber TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pgc_accounts (
                code TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL
            )
        """)
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('68100000', 'Amortización', 'gasto')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('28100000', 'Amortización Acumulada', 'pasivo')")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM ledger_entries")
        conn.commit()

    with patch("app.domain.services.ledger_service.LedgerService.is_fiscal_year_closed", return_value=False):
        res_apply = await generate_depreciation_proposal_tool(2026, confirmed_by_user=True)
        assert res_apply["status"] == "ok"
        assert "registrado con éxito" in res_apply["message"]
        
        # Validar inserción del asiento en la base de datos
        with _get_connection("default") as conn:
            row_journal = conn.execute("SELECT * FROM journal_entries LIMIT 1").fetchone()
            assert row_journal is not None
            assert row_journal["entry_date"] == "31/12/2026"
            
            row_ledger = conn.execute("SELECT * FROM ledger_entries").fetchall()
            assert len(row_ledger) == 2  # Un apunte al Debe y otro al Haber
