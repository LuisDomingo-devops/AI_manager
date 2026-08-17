import sqlite3

VERSION = "004"
DESCRIPTION = "Soft Delete en clientes y productos, periodos fiscales (TaxPeriods), gestor de tareas en background (Tasks) y consentimientos bancarios PSD2"

def upgrade(conn: sqlite3.Connection):
    # 1. Columnas de Soft Delete en clients
    try:
        conn.execute("ALTER TABLE clients ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE clients ADD COLUMN deleted_at TEXT")
    except sqlite3.OperationalError:
        pass

    # 2. Columnas de Soft Delete en products
    try:
        conn.execute("ALTER TABLE products ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE products ADD COLUMN deleted_at TEXT")
    except sqlite3.OperationalError:
        pass

    # 3. Columnas de consentimiento PSD2 en bank_connections
    try:
        conn.execute("ALTER TABLE bank_connections ADD COLUMN consent_expires_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE bank_connections ADD COLUMN consent_status TEXT NOT NULL DEFAULT 'valid'")
    except sqlite3.OperationalError:
        pass

    # 4. Tabla de Periodos Fiscales Formales (TaxPeriods)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_periods (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            year          INTEGER NOT NULL,
            quarter       INTEGER NOT NULL,
            model_name    TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'open',
            presented_at  TEXT,
            aeat_csv      TEXT,
            total_result  REAL DEFAULT 0.0,
            notes         TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 5. Tabla de Tareas en Background (Tasks)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id            TEXT PRIMARY KEY,
            task_type     TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            progress      REAL NOT NULL DEFAULT 0.0,
            goal          TEXT,
            payload       TEXT,
            result        TEXT,
            error         TEXT,
            client_id     TEXT NOT NULL DEFAULT 'default',
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
