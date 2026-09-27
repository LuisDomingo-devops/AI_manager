import sqlite3

VERSION = "023"
DESCRIPTION = "Add active_domain and last_intent to conversation_metadata"

def upgrade(conn: sqlite3.Connection) -> None:
    # Verificamos si las columnas ya existen antes de intentar añadirlas (idempotencia)
    cursor = conn.execute("PRAGMA table_info(conversation_metadata)")
    columns = [
        row["name"] if isinstance(row, dict) or hasattr(row, "keys") else row[1]
        for row in cursor.fetchall()
    ]
    
    if "active_domain" not in columns:
        conn.execute("ALTER TABLE conversation_metadata ADD COLUMN active_domain TEXT DEFAULT 'general'")
    
    if "last_intent" not in columns:
        conn.execute("ALTER TABLE conversation_metadata ADD COLUMN last_intent TEXT")
