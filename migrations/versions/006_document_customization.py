import sqlite3

VERSION = "006"
DESCRIPTION = "Tabla de personalización de documentos (logo, colores y plantillas)"

def upgrade(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS document_customization (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT NOT NULL DEFAULT 'default',
            logo_base64 TEXT,
            primary_color TEXT DEFAULT '#1E293B',
            secondary_color TEXT DEFAULT '#64748B',
            font_family TEXT DEFAULT 'Helvetica',
            layout_template TEXT DEFAULT 'classic',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_customization_client 
        ON document_customization (client_id)
    """)
