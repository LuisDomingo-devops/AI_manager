"""
Gestor Central de Conexiones y Pool Thread-Local para SQLite.
Feature: specs/020-sqlite-connection-pool-concurrency
"""

import contextlib
import contextvars
import logging
import os
import re
import sqlite3
import sys
import threading
from pathlib import Path
from typing import Dict, Generator, Optional, Set

from app.infrastructure.database.concurrency import tenant_locks

logger = logging.getLogger("connection_manager")

tenant_context = contextvars.ContextVar("tenant_context", default="default")

IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "true"

if IS_TESTING:
    DB_PATH = "file:main_mem"
elif os.getenv("ALFONSO_DB_PATH"):
    DB_PATH = Path(os.getenv("ALFONSO_DB_PATH"))
else:
    DB_PATH = Path(__file__).resolve().parents[3] / "data" / "memory.db"

DEFAULT_BUSY_TIMEOUT_MS = 60000
DEFAULT_TIMEOUT_SECONDS = 60.0

SQLITE_PRAGMAS = [
    "PRAGMA busy_timeout = 60000;",
    "PRAGMA journal_mode = WAL;",
    "PRAGMA synchronous = NORMAL;",
    "PRAGMA temp_store = MEMORY;",
]

_initialized_dbs: Set[str] = set()
_active_tenant = None
_test_dummy_conns: Dict[str, sqlite3.Connection] = {}
_schema_init_lock = threading.Lock()

# Almacenamiento thread-local para conexiones reutilizables por hilo
_thread_local = threading.local()


def _get_thread_connections() -> Dict[str, sqlite3.Connection]:
    if not hasattr(_thread_local, "connections"):
        _thread_local.connections = {}
    return _thread_local.connections


def _get_thread_readonly_connections() -> Dict[str, sqlite3.Connection]:
    if not hasattr(_thread_local, "readonly_connections"):
        _thread_local.readonly_connections = {}
    return _thread_local.readonly_connections


def reset_thread_local_pool() -> None:
    """Cierra las conexiones del hilo actual y limpia el almacenamiento thread-local."""
    conns = _get_thread_connections()
    for conn in list(conns.values()):
        try:
            conn.close()
        except Exception:
            pass
    conns.clear()

    ro_conns = _get_thread_readonly_connections()
    for conn in list(ro_conns.values()):
        try:
            conn.close()
        except Exception:
            pass
    ro_conns.clear()


def init_all_schemas(conn: sqlite3.Connection) -> None:
    """Delega la inicialización del esquema al MigrationRunner."""
    try:
        from app.infrastructure.database.migrations import MigrationRunner
        MigrationRunner.run_pending_migrations(conn)
    except Exception as e:
        logger.error(f"Error executing migrations: {e}")
        raise


def _resolve_target_path(client_id: Optional[str] = None):
    cid = (client_id or tenant_context.get()).strip().lower()
    sanitized_cid = re.sub(r"[^a-zA-Z0-9_-]", "", cid)
    if not sanitized_cid:
        sanitized_cid = "default"

    if IS_TESTING and isinstance(DB_PATH, str) and DB_PATH.startswith("file:"):
        if sanitized_cid == "default":
            target_path = f"{DB_PATH}?mode=memory&cache=shared"
        else:
            target_path = f"{DB_PATH}_{sanitized_cid}?mode=memory&cache=shared"
    else:
        if IS_TESTING:
            target_path = DB_PATH.parent / f"test_memory_{sanitized_cid}.db"
        else:
            target_path = DB_PATH.parent / f"memory_{sanitized_cid}.db"

    return target_path, sanitized_cid


def _get_connection(client_id: Optional[str] = None) -> sqlite3.Connection:
    """
    Retorna una conexión activa para el tenant solicitado, garantizando afinidad de hilo (thread-local).
    Configura pragmas de alto rendimiento y tolerancia a contención (busy_timeout=60000ms, WAL).
    """
    target_path, sanitized_cid = _resolve_target_path(client_id)
    db_key = str(target_path)
    thread_conns = _get_thread_connections()

    # Comprobar si existe una conexión abierta y sana en este hilo
    if db_key in thread_conns:
        existing_conn = thread_conns[db_key]
        try:
            existing_conn.execute("SELECT 1")
            return existing_conn
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            try:
                existing_conn.close()
            except Exception:
                pass
            thread_conns.pop(db_key, None)

    # Crear nueva conexión con timeouts y pragmas de alto rendimiento
    if not isinstance(target_path, str):
        if str(target_path) != ":memory:":
            target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(target_path),
            check_same_thread=False,
            timeout=DEFAULT_TIMEOUT_SECONDS
        )
    else:
        conn = sqlite3.connect(
            target_path,
            uri=True,
            check_same_thread=False,
            timeout=DEFAULT_TIMEOUT_SECONDS
        )

    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS};")

    if str(target_path) != ":memory:" and "?mode=memory" not in str(target_path):
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")

    # Inicialización atómica y segura del esquema ante llamadas concurrentes
    with _schema_init_lock:
        if db_key not in _initialized_dbs:
            if IS_TESTING and "?mode=memory" in db_key:
                _test_dummy_conns[db_key] = sqlite3.connect(db_key, uri=True, check_same_thread=False)
            init_all_schemas(conn)
            _initialized_dbs.add(db_key)

    thread_conns[db_key] = conn
    return conn


@contextlib.contextmanager
def write_transaction(client_id: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager transaccional para operaciones de escritura protegidas.
    Adquiere el cerrojo del tenant en Python para evitar colisiones a nivel de SQLite,
    y gestiona commit y rollback automáticos.
    """
    target_path, sanitized_cid = _resolve_target_path(client_id)
    lock = tenant_locks.get_lock(sanitized_cid)

    with lock:
        conn = _get_connection(client_id)
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise


def get_readonly_connection(client_id: Optional[str] = None) -> sqlite3.Connection:
    """
    Retorna una conexión thread-local configurada exclusivamente para lectura (PRAGMA query_only = ON).
    Permite a consultas analíticas o endpoints GET operar concurrentemente sin competir por bloqueos de escritura.
    """
    # Garantizar que la base de datos y sus tablas están inicializadas
    _get_connection(client_id)

    target_path, sanitized_cid = _resolve_target_path(client_id)
    db_key = str(target_path)
    thread_ro_conns = _get_thread_readonly_connections()

    if db_key in thread_ro_conns:
        existing_conn = thread_ro_conns[db_key]
        try:
            existing_conn.execute("SELECT 1")
            return existing_conn
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            try:
                existing_conn.close()
            except Exception:
                pass
            thread_ro_conns.pop(db_key, None)

    if not isinstance(target_path, str):
        conn = sqlite3.connect(
            str(target_path),
            check_same_thread=False,
            timeout=DEFAULT_TIMEOUT_SECONDS
        )
    else:
        conn = sqlite3.connect(
            target_path,
            uri=True,
            check_same_thread=False,
            timeout=DEFAULT_TIMEOUT_SECONDS
        )

    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DEFAULT_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA query_only = ON;")

    thread_ro_conns[db_key] = conn
    return conn
