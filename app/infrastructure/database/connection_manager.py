import os
import sys
import sqlite3
import contextvars
from pathlib import Path

tenant_context = contextvars.ContextVar("tenant_context", default="default")

IS_TESTING = "pytest" in sys.modules or os.getenv("TESTING") == "true"

if IS_TESTING:
    DB_PATH = "file:main_mem"
elif os.getenv("ALFONSO_DB_PATH"):
    DB_PATH = Path(os.getenv("ALFONSO_DB_PATH"))
else:
    DB_PATH = Path(__file__).resolve().parents[3] / "data" / "memory.db"

_initialized_dbs = set()
_active_tenant = None
_test_dummy_conns = {}

def init_all_schemas(conn: sqlite3.Connection) -> None:
    # Delegate 100% of schema initialization to the MigrationRunner
    try:
        from app.infrastructure.database.migrations import MigrationRunner
        MigrationRunner.run_pending_migrations(conn)
    except Exception as e:
        import logging
        logging.getLogger("migrations").error(f"Error executing migrations: {e}")
        raise

def _get_connection(client_id: str = None) -> sqlite3.Connection:
    global _active_tenant
    
    cid = (client_id or tenant_context.get()).strip().lower()
    
    import re
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
        
    if not isinstance(target_path, str):
        if str(target_path) != ":memory:":
            target_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target_path), check_same_thread=False)
    else:
        conn = sqlite3.connect(target_path, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    db_key = str(target_path)
    if db_key not in _initialized_dbs:
        if IS_TESTING and "?mode=memory" in db_key:
            _test_dummy_conns[db_key] = sqlite3.connect(db_key, uri=True, check_same_thread=False)
        init_all_schemas(conn)
        _initialized_dbs.add(db_key)
        
    return conn
