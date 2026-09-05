import sqlite3

def init_ai_memory_schema(conn: sqlite3.Connection) -> None:
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
    conn.commit()
