import sqlite3

def init_core_schema(conn: sqlite3.Connection) -> None:
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
    conn.commit()
