import sqlite3

VERSION = "003"
DESCRIPTION = "Trazabilidad de estados comerciales de Factura B2B (Ley Crea y Crece 18/2022) y cuentas PGC de retención IRPF"

def upgrade(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS b2b_invoice_status_history (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id     TEXT NOT NULL,
            status         TEXT NOT NULL,
            status_date    TEXT NOT NULL,
            reason         TEXT,
            payment_method TEXT,
            payment_date   TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Asegurar cuentas de retención en el catálogo PGC
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47300000', 'Hacienda Pública, retenciones y pagos a cuenta', 'activo')")
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47510000', 'Hacienda Pública, acreedora por retenciones practicadas', 'pasivo')")
