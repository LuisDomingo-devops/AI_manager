"""
Migración 014 — Tabla de usuario único y refresh tokens.

Un usuario por licencia. Las credenciales se almacenan con hash bcrypt.
Los refresh tokens se almacenan hasheados para revocación segura.
"""


def upgrade(conn) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_user (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            email         TEXT,
            password_hash TEXT NOT NULL,
            is_active     INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token_hash  TEXT PRIMARY KEY,
            expires_at  TEXT NOT NULL,
            revoked     INTEGER NOT NULL DEFAULT 0,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def downgrade(conn) -> None:
    conn.execute("DROP TABLE IF EXISTS refresh_tokens")
    conn.execute("DROP TABLE IF EXISTS app_user")
    conn.commit()


version = "014"
description = "Usuario único con bcrypt y refresh tokens para autenticación JWT"
