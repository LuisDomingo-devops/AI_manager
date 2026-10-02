"""
028_tax_declarations_retention_schema.py
========================================
Evolución del esquema para la custodia legal y archivo histórico de declaraciones tributarias.
Conforme a la Ley 58/2003 (General Tributaria, arts. 66 a 70) y Código de Comercio (art. 30).
Crea la tabla tax_declarations_ledger con plazo mínimo de retención obligatoria de 5 años.
"""
import sqlite3

VERSION = "028"
DESCRIPTION = "Tabla tax_declarations_ledger para custodia y retención legal de declaraciones por 5 años"


def upgrade(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    # 1. Asegurar o actualizar tabla tax_declarations_ledger
    cols_info = cursor.execute("PRAGMA table_info(tax_declarations_ledger)").fetchall()
    existing_cols = {c[1]: c[2] for c in cols_info} if cols_info else {}

    if not existing_cols:
        conn.execute("""
            CREATE TABLE tax_declarations_ledger (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id               TEXT NOT NULL DEFAULT 'default',
                model_code              TEXT NOT NULL,
                fiscal_year             INTEGER NOT NULL,
                period                  TEXT NOT NULL,
                declarant_nif           TEXT NOT NULL,
                declarant_name          TEXT NOT NULL DEFAULT '',
                casillas_json           TEXT NOT NULL DEFAULT '{}',
                boe_file_content        TEXT NOT NULL DEFAULT '',
                sha256_hash             TEXT NOT NULL,
                filing_status           TEXT NOT NULL DEFAULT 'CALCULATED',
                aeat_csv                TEXT,
                filing_date             TEXT NOT NULL,
                retention_until_date    TEXT NOT NULL,
                created_at              TEXT NOT NULL DEFAULT (datetime('now')),
                CONSTRAINT uq_tax_filing UNIQUE (tenant_id, model_code, fiscal_year, period)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tax_declarations_tenant_model_year
            ON tax_declarations_ledger (tenant_id, model_code, fiscal_year)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tax_declarations_retention
            ON tax_declarations_ledger (retention_until_date)
        """)
    else:
        # Añadir columnas que puedan faltar
        column_defs = {
            "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
            "declarant_name": "TEXT NOT NULL DEFAULT ''",
            "casillas_json": "TEXT NOT NULL DEFAULT '{}'",
            "boe_file_content": "TEXT NOT NULL DEFAULT ''",
            "sha256_hash": "TEXT NOT NULL DEFAULT ''",
            "filing_status": "TEXT NOT NULL DEFAULT 'CALCULATED'",
            "aeat_csv": "TEXT",
            "filing_date": "TEXT NOT NULL DEFAULT (datetime('now'))",
            "retention_until_date": "TEXT NOT NULL DEFAULT (datetime('now', '+5 years'))",
            "created_at": "TEXT NOT NULL DEFAULT (datetime('now'))"
        }
        for col_name, col_type in column_defs.items():
            if col_name not in existing_cols:
                conn.execute(f"ALTER TABLE tax_declarations_ledger ADD COLUMN {col_name} {col_type}")

    conn.commit()
