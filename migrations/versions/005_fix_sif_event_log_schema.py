import sqlite3

VERSION = "005"
DESCRIPTION = "Reconstrucción y normalización atómica del esquema SIF (sif_event_log) con current_hash y prev_event_hash"

def upgrade(conn: sqlite3.Connection):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sif_event_log'")
    table_exists = cursor.fetchone() is not None

    if not table_exists:
        conn.execute("""
            CREATE TABLE sif_event_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type      TEXT NOT NULL,
                description     TEXT NOT NULL,
                prev_event_hash TEXT,
                current_hash    TEXT NOT NULL,
                signature       TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        return

    # Si la tabla ya existe, verificar si requiere normalización estructural
    cursor.execute("PRAGMA table_info(sif_event_log)")
    cols = {row[1] for row in cursor.fetchall()}

    # Si falta current_hash o existen restricciones NOT NULL heredadas (ej. timestamp/event_hash),
    # realizamos una migración limpia mediante recreación de tabla
    desc_col = "description" if "description" in cols else ("payload" if "payload" in cols else "''")
    curr_col = "current_hash" if "current_hash" in cols else ("event_hash" if "event_hash" in cols else "''")
    prev_col = "prev_event_hash" if "prev_event_hash" in cols else ("previous_hash" if "previous_hash" in cols else "NULL")
    sig_col = "signature" if "signature" in cols else "''"
    created_col = "created_at" if "created_at" in cols else ("timestamp" if "timestamp" in cols else "datetime('now')")

    conn.execute("""
        CREATE TABLE sif_event_log_new (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type      TEXT NOT NULL,
            description     TEXT NOT NULL,
            prev_event_hash TEXT,
            current_hash    TEXT NOT NULL,
            signature       TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute(f"""
        INSERT INTO sif_event_log_new (id, event_type, description, prev_event_hash, current_hash, signature, created_at)
        SELECT id, event_type, {desc_col}, {prev_col}, {curr_col}, {sig_col}, {created_col}
        FROM sif_event_log
    """)

    conn.execute("DROP TABLE sif_event_log")
    conn.execute("ALTER TABLE sif_event_log_new RENAME TO sif_event_log")
