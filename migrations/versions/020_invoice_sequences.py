import sqlite3

VERSION = "020"
DESCRIPTION = "Tabla de secuencias para numeracion de facturas atomica"

def upgrade(conn: sqlite3.Connection):
    cursor = conn.cursor()
    
    # Crear la tabla de secuencias
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoice_sequences (
        year INTEGER NOT NULL,
        prefix TEXT NOT NULL,
        last_value INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (year, prefix)
    )
    """)
    
    conn.commit()
