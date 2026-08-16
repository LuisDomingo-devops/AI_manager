import sqlite3

VERSION = "001"
DESCRIPTION = "Esquema base inicial: conversaciones, memoria, facturación, cuentas PGC y conciliación bancaria"

def upgrade(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            client_id TEXT NOT NULL DEFAULT 'default'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            fact TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            client_id TEXT NOT NULL DEFAULT 'default'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            nif TEXT,
            razon_social TEXT,
            direccion TEXT,
            actividad_iae TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id     TEXT NOT NULL,
            date           TEXT NOT NULL,
            issuer_name    TEXT NOT NULL,
            issuer_nif     TEXT NOT NULL,
            receiver_name  TEXT,
            receiver_nif   TEXT,
            base_imponible REAL,
            iva_rate       REAL,
            iva_amount     REAL,
            irpf_rate      REAL,
            irpf_amount    REAL,
            total_amount   REAL NOT NULL,
            category       TEXT,
            quarter        INTEGER,
            year           INTEGER,
            file_path      TEXT,
            status         TEXT DEFAULT 'pending',
            concept        TEXT,
            blind_index    TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pgc_accounts (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            concept TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL,
            account_code TEXT NOT NULL,
            debe TEXT NOT NULL DEFAULT '0.0',
            haber TEXT NOT NULL DEFAULT '0.0',
            FOREIGN KEY(journal_entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY(account_code) REFERENCES pgc_accounts(code)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_connections (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            alias          TEXT NOT NULL,
            provider       TEXT NOT NULL,
            bank_name      TEXT,
            iban           TEXT,
            credentials    TEXT,
            status         TEXT DEFAULT 'active',
            last_sync_at   TEXT,
            created_at     TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_movements (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_date TEXT NOT NULL,
            concept       TEXT NOT NULL,
            amount        REAL NOT NULL,
            reference     TEXT,
            account_iban  TEXT,
            category      TEXT,
            connection_id INTEGER,
            is_reconciled INTEGER NOT NULL DEFAULT 0,
            reconciled_at TEXT,
            reconciled_invoice_id INTEGER,
            FOREIGN KEY (connection_id) REFERENCES bank_connections(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reconciliation_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            category TEXT NOT NULL,
            auto_apply INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_trail (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            payload    TEXT,
            timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            nif        TEXT NOT NULL,
            name       TEXT NOT NULL,
            email      TEXT,
            phone      TEXT,
            address    TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            unit_price  REAL NOT NULL,
            tax_rate    REAL NOT NULL DEFAULT 21.0,
            category    TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_number TEXT NOT NULL,
            client_id    INTEGER,
            quote_date   TEXT NOT NULL,
            valid_until  TEXT,
            status       TEXT DEFAULT 'draft',
            total_amount REAL NOT NULL,
            notes        TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(client_id) REFERENCES clients(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quote_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id    INTEGER NOT NULL,
            product_id  INTEGER,
            description TEXT NOT NULL,
            quantity    REAL NOT NULL,
            unit_price  REAL NOT NULL,
            tax_rate    REAL NOT NULL,
            subtotal    REAL NOT NULL,
            FOREIGN KEY(quote_id) REFERENCES quotes(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects_wip (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            status      TEXT DEFAULT 'active',
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks_wip (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            description TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY(project_id) REFERENCES projects_wip(id)
        )
    """)
