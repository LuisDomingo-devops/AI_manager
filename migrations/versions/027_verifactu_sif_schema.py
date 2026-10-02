"""
027_verifactu_sif_schema.py
============================
Evolución del esquema para cumplimiento estricto de Veri*factu y SIF (AEAT).
Conforme a la Ley 11/2021, RD 1007/2023 y Orden HAC/1177/2024.
Añade soporte multi-tenant, series segregadas, Decimal monetario en TEXT,
almacenamiento de XML validado, URL de QR reglamentario y Libro de Eventos SIF.
"""
import sqlite3

VERSION = "027"
DESCRIPTION = "Esquema completo Veri*factu SIF Orden HAC/1177/2024 (series, XML, QR, decimal TEXT)"


def upgrade(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    # 1. Asegurar o actualizar tabla verifactu_invoices
    cols_info = cursor.execute("PRAGMA table_info(verifactu_invoices)").fetchall()
    existing_cols = {c[1]: c[2] for c in cols_info} if cols_info else {}

    if not existing_cols:
        conn.execute("""
            CREATE TABLE verifactu_invoices (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id           TEXT NOT NULL DEFAULT 'default',
                series              TEXT NOT NULL DEFAULT 'F2026',
                number              INTEGER NOT NULL DEFAULT 1,
                issue_date          TEXT NOT NULL,
                issue_time          TEXT NOT NULL DEFAULT '00:00:00+01:00',
                invoice_type        TEXT NOT NULL DEFAULT 'F1',
                is_rectificativa    INTEGER NOT NULL DEFAULT 0,
                rectification_type  TEXT,
                rectified_series    TEXT,
                rectified_number    INTEGER,
                issuer_nif          TEXT NOT NULL,
                issuer_name         TEXT NOT NULL DEFAULT '',
                recipient_nif       TEXT,
                recipient_name      TEXT,
                base_amount         TEXT NOT NULL DEFAULT '0.00',
                tax_amount          TEXT NOT NULL DEFAULT '0.00',
                total_amount        TEXT NOT NULL DEFAULT '0.00',
                prev_hash           TEXT,
                current_hash        TEXT NOT NULL,
                signature           TEXT,
                qr_url              TEXT NOT NULL DEFAULT '',
                xml_content         TEXT NOT NULL DEFAULT '',
                status              TEXT NOT NULL DEFAULT 'LOCAL_RECORDED',
                aeat_csv            TEXT,
                aeat_response_xml   TEXT,
                retry_count         INTEGER NOT NULL DEFAULT 0,
                last_retry_at       TEXT,
                created_at          TEXT NOT NULL DEFAULT (datetime('now')),
                CONSTRAINT uq_invoice_tenant_series_num UNIQUE (tenant_id, series, number)
            )
        """)
    else:
        # Añadir columnas que puedan faltar en esquemas previos de desarrollo
        column_defs = {
            "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
            "series": "TEXT NOT NULL DEFAULT 'F2026'",
            "number": "INTEGER NOT NULL DEFAULT 1",
            "issue_date": "TEXT NOT NULL DEFAULT ''",
            "issue_time": "TEXT NOT NULL DEFAULT '00:00:00+01:00'",
            "invoice_type": "TEXT NOT NULL DEFAULT 'F1'",
            "is_rectificativa": "INTEGER NOT NULL DEFAULT 0",
            "rectification_type": "TEXT",
            "rectified_series": "TEXT",
            "rectified_number": "INTEGER",
            "issuer_name": "TEXT NOT NULL DEFAULT ''",
            "recipient_nif": "TEXT",
            "recipient_name": "TEXT",
            "invoice_number": "TEXT",
            "date_of_issue": "TEXT NOT NULL DEFAULT ''",
            "base_amount": "TEXT NOT NULL DEFAULT '0.00'",
            "tax_amount": "TEXT NOT NULL DEFAULT '0.00'",
            "qr_url": "TEXT NOT NULL DEFAULT ''",
            "xml_content": "TEXT NOT NULL DEFAULT ''",
            "aeat_csv": "TEXT",
            "aeat_response_xml": "TEXT",
            "last_retry_at": "TEXT"
        }
        for col_name, col_type in column_defs.items():
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE verifactu_invoices ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass

    # Índices para verifactu_invoices
    conn.execute("CREATE INDEX IF NOT EXISTS idx_verifactu_tenant_status ON verifactu_invoices(tenant_id, status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_verifactu_hash ON verifactu_invoices(current_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_verifactu_series_num ON verifactu_invoices(tenant_id, series, number)")

    # 2. Asegurar o actualizar tabla sif_event_log
    sif_cols_info = cursor.execute("PRAGMA table_info(sif_event_log)").fetchall()
    sif_existing_cols = {c[1]: c[2] for c in sif_cols_info} if sif_cols_info else {}

    if not sif_existing_cols:
        conn.execute("""
            CREATE TABLE sif_event_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id       TEXT NOT NULL DEFAULT 'default',
                event_type      TEXT NOT NULL,
                description     TEXT NOT NULL,
                prev_event_hash TEXT,
                current_hash    TEXT NOT NULL,
                signature       TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
    else:
        if "tenant_id" not in sif_existing_cols:
            try:
                conn.execute("ALTER TABLE sif_event_log ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
            except Exception:
                pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_sif_events_tenant_created ON sif_event_log(tenant_id, created_at)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sif_events_hash ON sif_event_log(current_hash)")
