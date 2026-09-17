import sqlite3
import logging
logger = logging.getLogger(__name__)

def upgrade(cursor: sqlite3.Cursor):
    try:
        cursor.execute("DROP TABLE IF EXISTS bank_transfers")
        logger.info("Migración 022 aplicada: Tabla bank_transfers eliminada (pagos PSD2 deprecados).")
    except Exception as e:
        logger.error(f"Error al eliminar bank_transfers: {e}")
        raise
