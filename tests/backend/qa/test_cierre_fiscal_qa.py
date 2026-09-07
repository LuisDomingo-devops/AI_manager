import pytest
from app.domain.services.closing_service import ClosingService
from app.adapters.memory.memory import _get_connection

def test_cierre_fiscal_qa_flujo_completo():
    """
    Test QA End-to-End para simular el cierre de un periodo fiscal por un usuario.
    """
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fiscal_year_status WHERE year = 2026")
    cursor.execute("DELETE FROM journal_entries WHERE entry_date LIKE '2026-%'")
    cursor.execute("DELETE FROM ledger_entries")
    
    # Usuario registró ventas
    cursor.execute("INSERT INTO journal_entries (id, concept, entry_date) VALUES (201, 'Venta QA', '2026-03-01 10:00:00')")
    cursor.execute("INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (201, '43000000', 121, 0)")
    cursor.execute("INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (201, '70000000', 0, 100)")
    cursor.execute("INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (201, '47700000', 0, 21)")
    
    conn.commit()
    
    # 1. Ejecutar cierre
    res = ClosingService.close_fiscal_year(2026)
    assert res["status"] == "ok"
    
    # 2. Intentar cerrar de nuevo debe fallar
    res2 = ClosingService.close_fiscal_year(2026)
    assert res2["status"] == "error"
    assert "ya se encuentra cerrado" in res2["message"]
    
    # 3. Comprobar base de datos
    cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = 2026")
    assert cursor.fetchone()["is_closed"] == 1
    
    # Cleanup para no afectar a otros tests
    cursor.execute("DELETE FROM fiscal_year_status WHERE year = 2026")
    conn.commit()
    conn.close()
