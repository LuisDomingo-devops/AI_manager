import sqlite3
import importlib
import pytest

migration_001 = importlib.import_module("migrations.versions.001_initial_core_schema")
upgrade = migration_001.upgrade

def test_migration_001_clean_db_creates_unified_schema_and_seeds(clean_db_conn):
    """Comprueba el aprovisionamiento limpio del esquema 001 unificado y la inicialización de seeds PGC."""
    # Ejecuta el upgrade en la conexión limpia
    upgrade(clean_db_conn)
    cursor = clean_db_conn.cursor()

    # 1. Verificar existencia y columnas canónicas en la tabla 'invoices'
    cursor.execute("PRAGMA table_info(invoices)")
    invoice_cols = {row[1]: row[2] for row in cursor.fetchall()}
    
    # Ambas versiones previas aportaban columnas que deben coexistir en el esquema canónico
    required_invoice_columns = [
        "id", "invoice_id", "date", "issuer_name", "issuer_nif",
        "receiver_name", "receiver_nif", "base_imponible", "iva_rate",
        "iva_amount", "irpf_rate", "irpf_amount", "total_amount",
        "status", "quarter", "year", "category", "concept",
        "file_path", "pdf_path", "xml_path", "is_recurrent",
        "recurrence_pattern", "blind_index", "contact_id",
        "verifactu_status", "hash", "tax_engine_version",
        "requires_manual_confirmation", "created_at"
    ]
    for col in required_invoice_columns:
        assert col in invoice_cols, f"Falta la columna canónica '{col}' en invoices"

    # 2. Verificar existencia y columnas canónicas en 'contacts'
    cursor.execute("PRAGMA table_info(contacts)")
    contact_cols = {row[1]: row[2] for row in cursor.fetchall()}
    for col in ["id", "name", "nif", "email", "phone", "address", "iban", "contact_type", "is_active", "created_at"]:
        assert col in contact_cols, f"Falta la columna canónica '{col}' en contacts"

    # 3. Verificar inicialización de cuentas PGC
    cursor.execute("SELECT code, name, type FROM pgc_accounts")
    pgc_rows = cursor.fetchall()
    assert len(pgc_rows) >= 12, f"Se esperaban al menos 12 cuentas PGC inicializadas, pero hay {len(pgc_rows)}"
    accounts = {row[0]: (row[1], row[2]) for row in pgc_rows}
    assert "43000000" in accounts, "La cuenta 43000000 (Clientes) debe estar presente"
    assert accounts["43000000"][1] == "activo"
    assert "70000000" in accounts, "La cuenta 70000000 (Ventas) debe estar presente"
    assert accounts["70000000"][1] == "ingreso"
    assert "47700021" in accounts, "La cuenta 47700021 (IVA Repercutido) debe estar presente"
    assert accounts["47700021"][1] == "pasivo"

    # 4. Verificar inicialización de subscription_status
    cursor.execute("SELECT tier, billing_cycle_start, extra_transfer_fee FROM subscription_status")
    sub = cursor.fetchone()
    assert sub is not None, "El estado de suscripción por defecto no fue inicializado"
    assert sub[0] in ("free", "basic")
    assert sub[2] == 0.50

    # 5. Comprobar inserción referencial entre contacto y factura
    cursor.execute("""
        INSERT INTO contacts (name, nif, email, contact_type)
        VALUES ('Cliente Prueba S.L.', 'B12345678', 'cliente@prueba.com', 'Cliente')
    """)
    contact_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO invoices (
            invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
            base_imponible, iva_rate, iva_amount, total_amount, quarter, year, contact_id
        ) VALUES (
            'FAC-2026-0001', '2026-09-30', 'Alfonso Autónomo', '12345678Z',
            'Cliente Prueba S.L.', 'B12345678', 1000.0, 21.0, 210.0, 1210.0, 3, 2026, ?
        )
    """, (contact_id,))
    invoice_id = cursor.lastrowid
    assert invoice_id > 0
    clean_db_conn.commit()
