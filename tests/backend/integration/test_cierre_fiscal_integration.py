import pytest
from app.domain.services.ledger_service import LedgerService
from app.adapters.memory.memory import _get_connection

def test_cierre_fiscal_db_integration():
    """
    Test de integración para comprobar que el cierre fiscal persiste correctamente los estados en la base de datos.
    """
    # 1. Preparar datos
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM fiscal_year_status WHERE year = 2026")
    cursor.execute("DELETE FROM journal_entries WHERE entry_date LIKE '2026-%'")
    cursor.execute("DELETE FROM ledger_entries")
    
    # Insertar cuentas PGC faltantes
    cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('70000000', 'Ventas de mercaderías', 'ingreso')")
    cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47700000', 'H.P. IVA repercutido', 'pasivo')")
    cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('60000000', 'Compras de mercaderías', 'gasto')")
    cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47200000', 'H.P. IVA soportado', 'activo')")
    cursor.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('41000000', 'Acreedores por prestaciones de servicios', 'pasivo')")
    
    from app.utils.encryption import encryptor
    
    def enc(val):
        return encryptor.encrypt(str(val))
        
    # Insertar un asiento de ingresos (700) y gastos (600)
    cursor.execute("INSERT INTO journal_entries (id, concept, entry_date) VALUES (101, 'Ventas', '2026-05-15 10:00:00')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (101, '43000000', '{enc(1210)}', '{enc(0)}')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (101, '70000000', '{enc(0)}', '{enc(1000)}')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (101, '47700000', '{enc(0)}', '{enc(210)}')")

    cursor.execute("INSERT INTO journal_entries (id, concept, entry_date) VALUES (102, 'Compras', '2026-06-20 10:00:00')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (102, '60000000', '{enc(500)}', '{enc(0)}')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (102, '47200000', '{enc(105)}', '{enc(0)}')")
    cursor.execute(f"INSERT INTO ledger_entries (journal_entry_id, account_code, debe, haber) VALUES (102, '41000000', '{enc(0)}', '{enc(605)}')")
    conn.commit()
    
    # 2. Ejecutar cierre
    res = LedgerService.close_fiscal_year(2026)
    print("CIERRE FISCAL RESULT:", res)
    assert res["status"] == "ok"
    assert res["resultado_ejercicio"] == 500.0 # Ingresos 1000 - Gastos 500
    
    # 3. Comprobar que está cerrado en BD
    cursor.execute("SELECT is_closed FROM fiscal_year_status WHERE year = 2026")
    row = cursor.fetchone()
    assert row["is_closed"] == 1
    
    # 4. Comprobar que el cierre fiscal generó el asiento a la 129
    # El concept está encriptado por LedgerService, así que buscamos todos y desciframos
    from app.utils.encryption import encryptor
    cursor.execute("SELECT id, concept FROM journal_entries")
    j_row = None
    for row in cursor.fetchall():
        try:
            concept = encryptor.decrypt(row["concept"])
            if concept == 'Asiento de Regularización de Ingresos y Gastos - Ejercicio 2026':
                j_row = row
                break
        except:
            if row["concept"] == 'Asiento de Regularización de Ingresos y Gastos - Ejercicio 2026':
                j_row = row
                break
                
    assert j_row is not None
    
    cursor.execute("SELECT * FROM ledger_entries WHERE journal_entry_id = ?", (j_row["id"],))
    entries = cursor.fetchall()
    
    accounts = []
    for e in entries:
        acct = encryptor.decrypt(e["account_code"]) if len(e["account_code"]) > 20 else e["account_code"]
        accounts.append(acct)
    
    assert "70000000" in accounts
    assert "60000000" in accounts
    assert "12900000" in accounts
    
    for e in entries:
        account = encryptor.decrypt(e["account_code"]) if len(e["account_code"]) > 20 else e["account_code"]
        if account == "12900000":
            haber_val = float(encryptor.decrypt(e["haber"])) if len(e["haber"]) > 20 else float(e["haber"])
            debe_val = float(encryptor.decrypt(e["debe"])) if len(e["debe"]) > 20 else float(e["debe"])
            assert haber_val == 500.0
            assert debe_val == 0.0
            
    # Cleanup para no afectar a otros tests
    cursor.execute("DELETE FROM fiscal_year_status WHERE year = 2026")
    conn.commit()
    conn.close()
