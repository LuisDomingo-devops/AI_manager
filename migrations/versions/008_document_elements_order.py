import sqlite3

VERSION = "008"
DESCRIPTION = "Columna elements_layout en la personalizacion de documentos para soportar drag and drop"

def upgrade(conn: sqlite3.Connection):
    try:
        conn.execute("ALTER TABLE document_customization ADD COLUMN elements_layout TEXT DEFAULT '[\"cabecera\", \"emisor_receptor\", \"detalles\", \"totales\", \"pie_verifactu\"]'")
    except sqlite3.OperationalError:
        pass
