import sqlite3

VERSION = "021"
DESCRIPTION = "Certificates table for advanced electronic signatures"

def upgrade(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            cert_type TEXT NOT NULL, -- 'SOFTWARE' or 'HARDWARE_REF'
            encrypted_p12 BLOB, -- the .p12 bytes encrypted (only for SOFTWARE)
            encrypted_password TEXT, -- the .p12 password encrypted (only for SOFTWARE)
            subject_name TEXT, -- Extracted name for UI display
            valid_from TEXT, -- ISO 8601 string
            valid_to TEXT, -- ISO 8601 string
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_certificates_tenant ON certificates(tenant_id);")
    conn.commit()
