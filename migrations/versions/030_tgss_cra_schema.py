"""
030_tgss_cra_schema.py
======================
Evolución del esquema para el registro y custodia de remesas mensuales CRA (Conceptos Retributivos Abonados)
generadas para la pasarela SILTRA de la Tesorería General de la Seguridad Social (Real Decreto-ley 16/2013).
Crea la tabla tgss_cra_records.
"""
import sqlite3

VERSION = "030"
DESCRIPTION = "Tabla tgss_cra_records para remesas mensuales CRA para SILTRA"


def upgrade(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    cols_info = cursor.execute("PRAGMA table_info(tgss_cra_records)").fetchall()
    existing_cols = {c[1]: c[2] for c in cols_info} if cols_info else {}

    if not existing_cols:
        conn.execute("""
            CREATE TABLE tgss_cra_records (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id       TEXT NOT NULL DEFAULT 'default',
                ccc             TEXT NOT NULL,
                month           INTEGER NOT NULL,
                year            INTEGER NOT NULL,
                file_path       TEXT NOT NULL,
                total_workers   INTEGER NOT NULL DEFAULT 0,
                xml_payload     TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'GENERATED',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                CONSTRAINT uq_tgss_cra UNIQUE (tenant_id, ccc, year, month)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tgss_cra_tenant_ccc_period
            ON tgss_cra_records (tenant_id, ccc, year, month)
        """)
    else:
        column_defs = {
            "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
            "ccc": "TEXT NOT NULL DEFAULT ''",
            "month": "INTEGER NOT NULL DEFAULT 1",
            "year": "INTEGER NOT NULL DEFAULT 2026",
            "file_path": "TEXT NOT NULL DEFAULT ''",
            "total_workers": "INTEGER NOT NULL DEFAULT 0",
            "xml_payload": "TEXT NOT NULL DEFAULT ''",
            "status": "TEXT NOT NULL DEFAULT 'GENERATED'",
            "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))"
        }
        for col_name, col_type in column_defs.items():
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE tgss_cra_records ADD COLUMN {col_name} {col_type}")

    conn.commit()
