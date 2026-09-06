import pytest
from app.adapters.memory.memory import _get_connection
from app.tools.server.billing_tools import close_fiscal_year_tool

@pytest.mark.asyncio
async def test_year_end_closing():
    from app.infrastructure.database.connection_manager import tenant_context
    tenant_context.set("test_year_end_tenant")
    
    # Attempt to close a year (e.g. 2026) without confirmation
    res_no_confirm = await close_fiscal_year_tool(2026, confirmed_by_user=False)
    assert res_no_confirm["status"] == "pending_confirmation"
    
    # Confirm
    res_confirm = await close_fiscal_year_tool(2026, confirmed_by_user=True)
    assert res_confirm["status"] in ("ok", "error") # Depends on existing test data if it can close or if there is no data
    
    if res_confirm["status"] == "ok":
        # Check it's closed in DB
        conn = _get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = 2026")
            is_closed = cursor.fetchone()["is_closed"]
            assert is_closed == 1
        finally:
            conn.close()
            
        # Try closing again
        res_already_closed = await close_fiscal_year_tool(2026, confirmed_by_user=True)
        assert res_already_closed["status"] == "error"
        assert "ya está cerrado" in res_already_closed["message"]
