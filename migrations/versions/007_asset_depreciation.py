import sqlite3

VERSION = "007"
DESCRIPTION = "Tabla de bienes de inversión y activos para cálculo de amortizaciones"

def upgrade(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL DEFAULT 'default',
            name TEXT NOT NULL,
            purchase_date TEXT NOT NULL,
            cost REAL NOT NULL,
            useful_life_years INTEGER NOT NULL,
            depreciation_method TEXT NOT NULL DEFAULT 'lineal',
            salvage_value REAL DEFAULT 0.0,
            category TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_assets_client 
        ON assets (client_id)
    """)
