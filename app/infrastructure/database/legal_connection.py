"""Gestor Exclusivo de Conexiones SQLite para el Núcleo Legal y Fiscal.

Garantiza aislamiento transaccional estricto, modo WAL y cerrojos inmediatos
para facturación oficial, PGC y encadenamiento VeriFactu (RD 1007/2023).
"""

import contextlib
import logging
import sqlite3
from typing import Generator, Optional

from app.infrastructure.database.connection_manager import (
    _get_connection,
    get_readonly_connection,
    tenant_context,
)
from app.infrastructure.database.concurrency import tenant_locks

logger = logging.getLogger("legal_connection")

LEGAL_BUSY_TIMEOUT_MS = 30000


def get_legal_connection(client_id: Optional[str] = None) -> sqlite3.Connection:
    """Obtiene una conexión dedicada al dominio legal con configuración segura."""
    conn = _get_connection(client_id=client_id)
    conn.execute(f"PRAGMA busy_timeout = {LEGAL_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def get_legal_readonly_connection(client_id: Optional[str] = None) -> sqlite3.Connection:
    """Obtiene una conexión de solo lectura para consultas de libros e informes."""
    return get_readonly_connection(client_id=client_id)


@contextlib.contextmanager
def legal_write_transaction(client_id: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager para transacciones atómicas exclusivas del núcleo legal.
    
    Aplica cerrojo de inquilino y transacción inmediata (BEGIN IMMEDIATE) para
    evitar condiciones de carrera en la correlatividad de facturas y encadenamiento.
    """
    cid = (client_id or tenant_context.get()).strip().lower()
    lock = tenant_locks.get_lock(cid)
    
    with lock:
        conn = get_legal_connection(client_id=cid)
        # Asegurar transacción inmediata
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error en transacción legal (revertida con rollback): {e}")
            raise
        finally:
            cursor.close()


@contextlib.contextmanager
def legal_read_transaction(client_id: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager para consultas de lectura en el dominio legal."""
    conn = get_legal_readonly_connection(client_id=client_id)
    try:
        yield conn
    finally:
        pass

