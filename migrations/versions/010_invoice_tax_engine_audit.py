import sqlite3

VERSION = "010"
DESCRIPTION = "Añadir campos de auditoría del motor fiscal a facturas (tax_engine_version y requires_manual_confirmation)"

def upgrade(conn: sqlite3.Connection):
    # Añadir tax_engine_version
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN tax_engine_version TEXT")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise e

    # Añadir requires_manual_confirmation
    try:
        conn.execute("ALTER TABLE invoices ADD COLUMN requires_manual_confirmation INTEGER DEFAULT 0")
    except sqlite3.OperationalError as e:
        if "duplicate column name" not in str(e).lower():
            raise e

def downgrade(conn: sqlite3.Connection):
    pass
