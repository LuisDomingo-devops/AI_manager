import pytest
from app.adapters.memory.asset_repository import MemoryAssetRepository
from app.domain.services.depreciation_service import DepreciationService
from app.domain.services.ledger_service import LedgerService
from app.infrastructure.database.memory.memory import tenant_context

@pytest.fixture(autouse=True)
def setup_context():
    tenant_context.set("test_amortization_tenant")
    yield

def test_amortization_flow():
    client_id = tenant_context.get()
    from app.infrastructure.database.memory.memory import _get_connection
    with _get_connection(client_id) as conn:
        conn.execute("DELETE FROM assets")
        conn.execute("DELETE FROM journal_entries")
        conn.commit()
    repo = MemoryAssetRepository()
    ds = DepreciationService(repo)
    
    # 1. Add asset mid-year (July 1, 2026) -> Should prorrate 6 months
    asset_id = repo.save_asset(client_id, {
        "name": "MacBook Pro",
        "purchase_date": "2026-07-01",
        "cost": 2000.0,
        "salvage_value": 0.0,
        "useful_life_years": 4
    })
    
    # 2. Get amortization table for 2026
    proposal = ds.calculate_depreciation_proposal(client_id, 2026)
    assert len(proposal) == 1
    # Full year is 500, but bought in July so it's ~250
    assert abs(proposal[0]["amount"] - 250.0) < 5.0
    
    # 3. Execute amortization
    res = ds.record_depreciation_entries(client_id, 2026)
    assert res["status"] == "ok"
    assert res["total_amount"] > 0
    
    # 4. Check Balance de Situación
    balance = LedgerService.get_balance_situacion(2026)
    assert balance is not None
    # Activo (or pasivo depending on the exact implementation, usually in activo negative or in amort. account)
    # Just checking it doesn't crash
    assert "activo" in balance
    assert "pasivo_patrimonio" in balance
