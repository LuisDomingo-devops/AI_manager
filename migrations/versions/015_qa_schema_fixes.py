"""
015_qa_schema_fixes.py
======================
Migración de 'catch-up' para solucionar los fallos en la suite de pruebas debido
a la pérdida de tablas y columnas que se creaban de forma ad-hoc (inline) tras la 
transición a MigrationRunner.

Tablas recuperadas:
- conversation_metadata
- session_diary
- subscription_status

Columnas recuperadas:
- quote_id en quotes
- reconciled en bank_movements
"""

import sqlite3

version = "015"
description = "QA Schema Fixes (conversation_metadata, session_diary, subscription_status, missing columns)"


def upgrade(conn: sqlite3.Connection) -> None:
    # 1. Tabla conversation_metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_metadata (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            discipline TEXT,
            project_name TEXT,
            is_persistent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 2. Tabla session_diary
    conn.execute("""
        CREATE TABLE IF NOT EXISTS session_diary (
            date TEXT PRIMARY KEY,
            summary TEXT,
            messages TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 3. Tabla subscription_status
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscription_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tier TEXT NOT NULL DEFAULT 'basic',
            billing_cycle_start TEXT,
            extra_transfer_fee REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # 3.1. Tabla messages
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            client_id TEXT NOT NULL DEFAULT 'default',
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # 3.2. Tabla payments
    conn.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT NOT NULL,
            invoice_id TEXT NOT NULL,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # 3.3. Tabla bank_transfers
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bank_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transfer_date TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_iban TEXT NOT NULL,
            amount REAL NOT NULL,
            concept TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            extra_charge REAL NOT NULL DEFAULT 0.0,
            connection_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 3.4. Tabla invoices
    conn.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT NOT NULL,
            date TEXT NOT NULL,
            issuer_name TEXT NOT NULL,
            issuer_nif TEXT NOT NULL,
            receiver_name TEXT NOT NULL,
            receiver_nif TEXT NOT NULL,
            base_imponible REAL NOT NULL,
            iva_rate REAL NOT NULL,
            iva_amount REAL NOT NULL,
            irpf_rate REAL NOT NULL DEFAULT 0.0,
            irpf_amount REAL NOT NULL DEFAULT 0.0,
            total_amount REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'borrador',
            quarter INTEGER NOT NULL,
            year INTEGER NOT NULL,
            category TEXT NOT NULL DEFAULT 'ingreso',
            pdf_path TEXT,
            xml_path TEXT,
            is_recurrent INTEGER NOT NULL DEFAULT 0,
            recurrence_pattern TEXT,
            blind_index TEXT,
            verifactu_status TEXT,
            hash TEXT,
            tax_engine_version TEXT,
            requires_manual_confirmation INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 3.5. Tabla emails
    conn.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            sender TEXT,
            recipient TEXT,
            body TEXT,
            date TEXT,
            received_at TEXT,
            category TEXT,
            status TEXT NOT NULL DEFAULT 'received',
            attachments TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 3.6. Tabla settings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # 3.7. Tabla calendar_events
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calendar_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            start_time TEXT,
            end_time TEXT,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # 3.8. Tabla contacts
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            nif TEXT,
            email TEXT,
            phone TEXT,
            address TEXT,
            iban TEXT,
            contact_type TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 4. Modificar quotes añadiendo columnas faltantes
    for col_def in [
        "quote_id TEXT",
        "date TEXT",
        "client_name TEXT",
        "client_nif TEXT",
        "invoice_id TEXT",
        "base_imponible REAL NOT NULL DEFAULT 0.0",
        "iva_rate REAL NOT NULL DEFAULT 21.0",
        "iva_amount REAL NOT NULL DEFAULT 0.0",
        "irpf_rate REAL NOT NULL DEFAULT 0.0",
        "irpf_amount REAL NOT NULL DEFAULT 0.0",
        "concept TEXT",
        "file_path TEXT",
        "status TEXT NOT NULL DEFAULT 'draft'", 
        "quote_number TEXT", 
        "quote_date TEXT", 
        "valid_until TEXT", 
        "subtotal REAL NOT NULL DEFAULT 0.0", 
        "total_amount REAL NOT NULL DEFAULT 0.0", 
        "notes TEXT", 
        "created_at TEXT", 
        "updated_at TEXT", 
        "tenant_id TEXT",
        "signature TEXT"
    ]:
        try:
            conn.execute(f"ALTER TABLE quotes ADD COLUMN {col_def};")
        except sqlite3.OperationalError:
            pass

    # 5. Modificar bank_movements añadiendo columnas faltantes
    for col_def in [
        "reconciled INTEGER NOT NULL DEFAULT 0",
        "invoice_id TEXT"
    ]:
        try:
            conn.execute(f"ALTER TABLE bank_movements ADD COLUMN {col_def};")
        except sqlite3.OperationalError:
            pass

    # 6. Modificar products añadiendo campos perdidos
    for col_def in [
        "sku TEXT", 
        "stock INTEGER NOT NULL DEFAULT 0", 
        "item_type TEXT NOT NULL DEFAULT 'product'", 
        "is_active INTEGER NOT NULL DEFAULT 1", 
        "deleted_at TEXT",
        "price REAL NOT NULL DEFAULT 0.0",
        "iva_rate REAL NOT NULL DEFAULT 21.0"
    ]:
        try:
            conn.execute(f"ALTER TABLE products ADD COLUMN {col_def};")
        except sqlite3.OperationalError:
            pass

    # Añadir índice único para SKU en products
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_products_sku ON products(sku);")
    except sqlite3.OperationalError:
        pass

    # 7. Modificar bank_connections añadiendo is_default_remittance
    try:
        conn.execute("ALTER TABLE bank_connections ADD COLUMN is_default_remittance INTEGER NOT NULL DEFAULT 0;")
    except sqlite3.OperationalError:
        pass

    conn.commit()


def downgrade(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE IF EXISTS conversation_metadata")
    conn.execute("DROP TABLE IF EXISTS session_diary")
    conn.execute("DROP TABLE IF EXISTS subscription_status")
    
    # SQLite 3.35+ soporta DROP COLUMN
    try:
        conn.execute("ALTER TABLE quotes DROP COLUMN quote_id")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE bank_movements DROP COLUMN reconciled")
    except sqlite3.OperationalError:
        pass

    conn.commit()
