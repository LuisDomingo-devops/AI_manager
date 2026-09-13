import sqlite3

VERSION = "001"
DESCRIPTION = "Esquema inicial correcto"

def upgrade(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type     TEXT NOT NULL,
            nif           TEXT NOT NULL,
            razon_social  TEXT NOT NULL,
            direccion     TEXT,
            cert_path     TEXT,
            cert_password TEXT,
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            client_name   TEXT NOT NULL,
            client_nif    TEXT NOT NULL,
            budget        REAL NOT NULL,
            status        TEXT NOT NULL DEFAULT 'en_progreso',
            description   TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE,
            nif           TEXT NOT NULL,
            email         TEXT NOT NULL,
            phone         TEXT,
            address       TEXT,
            iban          TEXT,
            contact_type  TEXT NOT NULL DEFAULT 'Cliente',
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS assets (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id           TEXT NOT NULL DEFAULT 'default',
            name                TEXT NOT NULL,
            purchase_date       TEXT NOT NULL,
            cost                REAL NOT NULL,
            salvage_value       REAL NOT NULL DEFAULT 0.0,
            useful_life_years   INTEGER NOT NULL,
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id      TEXT,
            date            TEXT,
            issuer_name     TEXT,
            issuer_nif      TEXT,
            receiver_name   TEXT,
            receiver_nif    TEXT,
            base_imponible  REAL,
            iva_rate        REAL,
            iva_amount      REAL,
            irpf_rate       REAL,
            irpf_amount     REAL,
            total_amount    REAL,
            category        TEXT,
            quarter         INTEGER,
            year            INTEGER,
            file_path       TEXT,
            status          TEXT DEFAULT 'firmada',
            concept         TEXT,
            blind_index     TEXT,
            contact_id      INTEGER,
            tax_engine_version TEXT,
            requires_manual_confirmation INTEGER DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id        TEXT NOT NULL UNIQUE,
            date            TEXT NOT NULL,
            client_name     TEXT NOT NULL,
            client_nif      TEXT NOT NULL,
            base_imponible  TEXT NOT NULL,
            iva_rate        TEXT NOT NULL,
            iva_amount      TEXT NOT NULL,
            irpf_rate       TEXT NOT NULL,
            irpf_amount     TEXT NOT NULL,
            total_amount    TEXT NOT NULL,
            concept         TEXT NOT NULL,
            file_path       TEXT,
            status          TEXT DEFAULT 'borrador',
            signature       TEXT,
            contact_id      INTEGER,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sku           TEXT NOT NULL UNIQUE,
            name          TEXT NOT NULL,
            description   TEXT,
            price         REAL NOT NULL,
            iva_rate      REAL NOT NULL DEFAULT 21.0,
            stock         INTEGER DEFAULT 0,
            item_type     TEXT DEFAULT 'product',
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id      TEXT NOT NULL UNIQUE,
            invoice_id      TEXT NOT NULL,
            date            TEXT NOT NULL,
            amount          REAL NOT NULL,
            payment_method  TEXT NOT NULL,
            notes           TEXT,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id             INTEGER NOT NULL,
            product_id             INTEGER,
            description_override   TEXT NOT NULL,
            quantity               INTEGER NOT NULL,
            unit_price             REAL NOT NULL,
            subtotal               REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quote_items (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id               INTEGER NOT NULL,
            product_id             INTEGER,
            description_override   TEXT NOT NULL,
            quantity               INTEGER NOT NULL,
            unit_price             REAL NOT NULL,
            subtotal               REAL NOT NULL,
            FOREIGN KEY(quote_id) REFERENCES quotes(id),
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_invoices_blind_index
        ON invoices (blind_index)
    """)
    # Migrations fallback if items tables are empty
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM invoice_items")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id, concept, base_imponible FROM invoices")
        invoices = cursor.fetchall()
        for inv in invoices:
            inv_id, concept, base = inv
            if concept and base is not None:
                try:
                    b = float(base)
                    cursor.execute(
                        "INSERT INTO invoice_items (invoice_id, description_override, quantity, unit_price, subtotal) VALUES (?, ?, 1, ?, ?)",
                        (inv_id, concept, b, b)
                    )
                except (ValueError, TypeError):
                    pass
    cursor.execute("SELECT COUNT(*) FROM quote_items")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT id, concept, base_imponible FROM quotes")
        quotes = cursor.fetchall()
        for q in quotes:
            q_id, concept, base = q
            if concept and base is not None:
                try:
                    b = float(base)
                    cursor.execute(
                        "INSERT INTO quote_items (quote_id, description_override, quantity, unit_price, subtotal) VALUES (?, ?, 1, ?, ?)",
                        (q_id, concept, b, b)
                    )
                except ValueError:
                    pass
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
            ("21700000", "Equipos para procesos de informaciÃ³n", "activo"),
            ("40000000", "Proveedores (Acreedores comerciales)", "pasivo"),
            ("43000000", "Clientes", "activo"),
            ("47200021", "Hacienda PÃºblica, IVA soportado al 21%", "activo"),
            ("47300000", "Hacienda PÃºblica, retenciones y pagos a cuenta", "activo"),
            ("47510000", "Hacienda PÃºblica, acreedora por retenciones practicadas", "pasivo"),
            ("47700021", "Hacienda PÃºblica, IVA repercutido al 21%", "pasivo"),
            ("57000000", "Caja, euros (efectivo)", "activo"),
            ("57200001", "Banco de la empresa (cuenta corriente)", "activo"),
            ("60000000", "Compras de mercaderÃ­as / suministros", "gasto"),
            ("62900000", "Otros servicios / Gastos diversos", "gasto"),
            ("70000000", "Ventas de mercaderÃ­as", "ingreso"),
            ("70500000", "PrestaciÃ³n de servicios de consultorÃ­a/desarrollo", "ingreso"),
        ]
        cursor.executemany("INSERT INTO pgc_accounts (code, name, type) VALUES (?, ?, ?)", default_accounts)
    else:
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('12900000', 'Resultado del ejercicio', 'patrimonio')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47300000', 'Hacienda PÃºblica, retenciones y pagos a cuenta', 'activo')")
        conn.execute("INSERT OR IGNORE INTO pgc_accounts (code, name, type) VALUES ('47510000', 'Hacienda PÃºblica, acreedora por retenciones practicadas', 'pasivo')")
        
    cursor.execute("SELECT COUNT(*) FROM subscription_status")
    if cursor.fetchone()[0] == 0:
        import datetime
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        cursor.execute("INSERT INTO subscription_status (tier, billing_cycle_start, extra_transfer_fee) VALUES ('free', ?, 0.50)", (today_str,))
        
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT    NOT NULL,
            client_id   TEXT    NOT NULL DEFAULT 'default',
            role        TEXT    NOT NULL,
            content     TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_metadata (
            session_id   TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            discipline   TEXT NOT NULL DEFAULT 'general',
            project_name TEXT DEFAULT 'default',
            is_persistent INTEGER DEFAULT 1,
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_diary (
            date          TEXT PRIMARY KEY,
            summary       TEXT,
            messages      TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages (session_id, client_id, id)
    """)
