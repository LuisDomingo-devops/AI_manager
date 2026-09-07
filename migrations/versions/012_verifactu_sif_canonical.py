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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verifactu_invoices (
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sif_event_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type      TEXT NOT NULL,
            description     TEXT NOT NULL,
            prev_event_hash TEXT,
            current_hash    TEXT NOT NULL,
            signature       TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
