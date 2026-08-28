import sqlite3

VERSION = "009"
DESCRIPTION = "Columnas independientes para el layout de presupuestos y el ancho de logotipo ajustable"

def upgrade(conn: sqlite3.Connection):
    # Añadir quote_elements_layout
    try:
        conn.execute("ALTER TABLE document_customization ADD COLUMN quote_elements_layout TEXT DEFAULT '[\"cabecera\", \"emisor_receptor\", \"detalles\", \"totales\", \"pie_verifactu\"]'")
    except sqlite3.OperationalError:
        pass
        
    # Añadir logo_width
    try:
        conn.execute("ALTER TABLE document_customization ADD COLUMN logo_width INTEGER DEFAULT 110")
    except sqlite3.OperationalError:
        pass
