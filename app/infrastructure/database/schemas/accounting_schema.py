import sqlite3

def init_accounting_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pgc_accounts (
            code        TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            type        TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date  TEXT NOT NULL,
            concept     TEXT NOT NULL,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            journal_entry_id INTEGER NOT NULL,
            account_code     TEXT NOT NULL,
            debe             TEXT NOT NULL,
            haber            TEXT NOT NULL,
            FOREIGN KEY(journal_entry_id) REFERENCES journal_entries(id),
            FOREIGN KEY(account_code) REFERENCES pgc_accounts(code)
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_connections (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            alias          TEXT NOT NULL,
            provider       TEXT NOT NULL,
            bank_name      TEXT,
            iban           TEXT,
            credentials    TEXT,
            status         TEXT DEFAULT 'active',
            is_default_remittance INTEGER DEFAULT 0,
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
            invoice_id    TEXT,
            reconciled    INTEGER DEFAULT 0,
            connection_id INTEGER REFERENCES bank_connections(id),
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscription_status (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            tier                  TEXT NOT NULL DEFAULT 'free',
            billing_cycle_start   TEXT NOT NULL,
            extra_transfer_fee    REAL NOT NULL DEFAULT 0.50
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transfers (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_date       TEXT NOT NULL,
            recipient_name      TEXT NOT NULL,
            recipient_iban      TEXT NOT NULL,
            amount              REAL NOT NULL,
            concept             TEXT,
            status              TEXT DEFAULT 'initiated',
            extra_charge        REAL DEFAULT 0.00,
            connection_id       INTEGER REFERENCES bank_connections(id)
        )
    """)
    
    # Defaults
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pgc_accounts")
    if cursor.fetchone()[0] == 0:
        default_accounts = [
            ("10000000", "Capital Social", "patrimonio"),
            ("12900000", "Resultado del ejercicio", "patrimonio"),
            ("21700000", "Equipos para procesos de información", "activo"),
            ("40000000", "Proveedores (Acreedores comerciales)", "pasivo"),
            ("43000000", "Clientes", "activo"),
            ("47200021", "Hacienda Pública, IVA soportado al 21%", "activo"),
            ("47300000", "Hacienda Pública, retenciones y pagos a cuenta", "activo"),
            ("47510000", "Hacienda Pública, acreedora por retenciones practicadas", "pasivo"),
            ("47700021", "Hacienda Pública, IVA repercutido al 21%", "pasivo"),
            ("57000000", "Caja, euros (efectivo)", "activo"),
            ("57200001", "Banco de la empresa (cuenta corriente)", "activo"),
            ("60000000", "Compras de mercaderías / suministros", "gasto"),
            ("62900000", "Otros servicios / Gastos diversos", "gasto"),
            ("70000000", "Ventas de mercaderías", "ingreso"),
            ("70500000", "Prestación de servicios de consultoría/desarrollo", "ingreso"),
        ]
        cursor.executemany("INSERT INTO pgc_accounts (code, name, type) VALUES (?, ?, ?)", default_accounts)
    else:
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('12900000', 'Resultado del ejercicio', 'patrimonio')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47300000', 'Hacienda Pública, retenciones y pagos a cuenta', 'activo')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47510000', 'Hacienda Pública, acreedora por retenciones practicadas', 'pasivo')")
        
    cursor.execute("SELECT COUNT(*) FROM subscription_status")
    if cursor.fetchone()[0] == 0:
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO subscription_status (tier, billing_cycle_start, extra_transfer_fee) VALUES ('free', ?, 0.50)", (today_str,))
        
    conn.commit()
