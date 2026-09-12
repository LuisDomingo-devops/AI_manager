"""
012_verifactu_sif_canonical.py
================================
Migra la definicion canonica de las tablas Verifactu y SIF al MigrationRunner.
Antes era responsabilidad de VerifactuService.init_verifactu_schema().
"""
import sqlite3

VERSION = "012"
DESCRIPTION = "Esquema Verifactu/SIF: verifactu_invoices, sif_event_log"


def upgrade(conn: sqlite3.Connection) -> None:
    # Migracion de verifactu_invoices
    cursor = conn.cursor()
    cols_info = cursor.execute("PRAGMA table_info(verifactu_invoices)").fetchall()
    col_names = [c[1] for c in cols_info] if cols_info else []
    
    if not col_names:
        # No existe, crearla directamente
        conn.execute("""
            CREATE TABLE verifactu_invoices (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number    TEXT NOT NULL UNIQUE,
                date_of_issue     TEXT NOT NULL,
                issuer_nif        TEXT NOT NULL,
                receiver_nif      TEXT NOT NULL DEFAULT '',
                base_imponible    REAL NOT NULL DEFAULT 0.0,
                iva_amount        REAL NOT NULL DEFAULT 0.0,
                total_amount      REAL NOT NULL,
                prev_hash         TEXT,
                current_hash      TEXT NOT NULL,
                signature         TEXT,
                status            TEXT NOT NULL DEFAULT 'ALTA',
                delivery_status   TEXT DEFAULT 'PENDIENTE',
                delivery_error    TEXT,
                csv               TEXT,
                aeat_error_code   TEXT,
                aeat_error_desc   TEXT,
                aeat_response_raw TEXT,
                retry_count       INTEGER DEFAULT 0,
                last_attempt_at   TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
    elif "invoice_hash" in col_names and "current_hash" not in col_names:
        # Existe el esquema viejo, migrar
        conn.execute("""
            CREATE TABLE verifactu_invoices_migration (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number  TEXT NOT NULL UNIQUE,
                date_of_issue   TEXT NOT NULL,
                issuer_nif      TEXT NOT NULL,
                receiver_nif    TEXT NOT NULL DEFAULT '',
                base_imponible  REAL NOT NULL DEFAULT 0.0,
                iva_amount      REAL NOT NULL DEFAULT 0.0,
                total_amount    REAL NOT NULL,
                prev_hash       TEXT,
                current_hash    TEXT NOT NULL,
                signature       TEXT,
                status          TEXT NOT NULL DEFAULT 'ALTA',
                delivery_status TEXT DEFAULT 'PENDIENTE',
                delivery_error  TEXT,
                csv             TEXT,
                aeat_error_code TEXT,
                aeat_error_desc TEXT,
                aeat_response_raw TEXT,
                retry_count     INTEGER DEFAULT 0,
                last_attempt_at TEXT,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO verifactu_invoices_migration (
                id, invoice_number, date_of_issue, issuer_nif, total_amount,
                prev_hash, current_hash, signature, status, created_at
            ) SELECT id, invoice_number, date_of_issue, issuer_nif, total_amount,
                previous_hash, invoice_hash, signed_xml, status, created_at
              FROM verifactu_invoices
        """)
        conn.execute("DROP TABLE verifactu_invoices")
        conn.execute("ALTER TABLE verifactu_invoices_migration RENAME TO verifactu_invoices")

    # Migracion de sif_event_log
    cols_info = cursor.execute("PRAGMA table_info(sif_event_log)").fetchall()
    col_names = [c[1] for c in cols_info] if cols_info else []
    
    if not col_names:
        # No existe, crearla directamente
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
    elif "event_hash" in col_names and "current_hash" not in col_names:
        # Existe el esquema viejo, migrar
        conn.execute("""
            CREATE TABLE sif_event_log_migration (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type      TEXT NOT NULL,
                description     TEXT NOT NULL,
                prev_event_hash TEXT,
                current_hash    TEXT NOT NULL,
                signature       TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            INSERT INTO sif_event_log_migration (
                id, event_type, description, prev_event_hash, current_hash, signature, created_at
            ) SELECT id, event_type, payload, previous_hash, event_hash, signature, created_at
              FROM sif_event_log
        """)
        conn.execute("DROP TABLE sif_event_log")
        conn.execute("ALTER TABLE sif_event_log_migration RENAME TO sif_event_log")
