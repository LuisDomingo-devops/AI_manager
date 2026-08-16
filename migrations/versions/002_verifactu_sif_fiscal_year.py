import sqlite3

VERSION = "002"
DESCRIPTION = "Esquema Veri*Factu, registro de auditoría del SIF (Orden HAC/1177/2024) y control de cierre de ejercicio contable"

def upgrade(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verifactu_invoices (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number    TEXT UNIQUE NOT NULL,
            date_of_issue     TEXT NOT NULL,
            issuer_nif        TEXT NOT NULL,
            total_amount      REAL NOT NULL,
            invoice_hash      TEXT NOT NULL,
            previous_hash     TEXT NOT NULL,
            qr_code_content   TEXT NOT NULL,
            signed_xml        TEXT NOT NULL,
            status            TEXT DEFAULT 'registered',
            anulacion_id      TEXT,
            created_at        TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sif_event_log (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type        TEXT NOT NULL,
            timestamp         TEXT NOT NULL,
            payload           TEXT NOT NULL,
            event_hash        TEXT NOT NULL,
            previous_hash     TEXT NOT NULL,
            signature         TEXT NOT NULL,
            created_at        TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fiscal_year_status (
            year        INTEGER PRIMARY KEY,
            is_closed   INTEGER NOT NULL DEFAULT 0,
            closed_at   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Asegurar cuenta de resultado del ejercicio
    conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('12900000', 'Resultado del ejercicio', 'patrimonio')")
