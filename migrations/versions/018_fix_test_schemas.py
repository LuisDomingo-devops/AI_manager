import sqlite3

VERSION = "018"
DESCRIPTION = "Add missing columns and tables needed by tests due to legacy schema differences"

def upgrade(conn: sqlite3.Connection) -> None:
    # 1. products missing columns
    try:
        conn.execute("ALTER TABLE products ADD COLUMN unit_price REAL NOT NULL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
        
    try:
        conn.execute("ALTER TABLE products ADD COLUMN tax_rate REAL NOT NULL DEFAULT 21.0")
    except sqlite3.OperationalError:
        pass
        
    # 2. clients table
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
    
    # 3. conversations and facts tables
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
    
    # 4. assets missing column
    try:
        conn.execute("ALTER TABLE assets ADD COLUMN depreciation_method TEXT NOT NULL DEFAULT 'lineal'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE assets ADD COLUMN category TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE assets ADD COLUMN updated_at TEXT NOT NULL DEFAULT (datetime('now'))")
    except sqlite3.OperationalError:
        pass
