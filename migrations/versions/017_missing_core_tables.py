def upgrade(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER,
            description_override TEXT,
            quantity REAL NOT NULL DEFAULT 1.0,
            unit_price REAL NOT NULL DEFAULT 0.0,
            subtotal REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            invoice_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT,
            notes TEXT,
            FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_date TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_iban TEXT NOT NULL,
            amount REAL NOT NULL,
            concept TEXT,
            status TEXT DEFAULT 'initiated',
            extra_charge REAL DEFAULT 0.0,
            connection_id INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscription_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tier TEXT NOT NULL DEFAULT 'free',
            billing_cycle_start TEXT,
            extra_transfer_fee REAL DEFAULT 0.0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nif TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            iban TEXT,
            contact_type TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            client_name TEXT,
            client_nif TEXT,
            budget REAL,
            status TEXT,
            description TEXT
        )
    """)

def downgrade(conn):
    pass
