import sqlite3

def init_billing_schema(conn: sqlite3.Connection) -> None:
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
    conn.commit()
