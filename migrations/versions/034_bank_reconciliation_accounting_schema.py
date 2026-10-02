"""
034_bank_reconciliation_accounting_schema.py
============================================
Evolución de esquema para la conciliación bancaria y asientos contables PGC (Spec 034).
Crea la tabla bank_statements y amplía bank_movements con columnas de trazabilidad contable
(statement_id, account_iban, value_date, balance_after, journal_entry_id, reconciled_invoice_id, reconciliation_status).
"""
import sqlite3

VERSION = "034"
DESCRIPTION = "Esquema para extractos bancarios bank_statements y trazabilidad contable en bank_movements"


def upgrade(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()

    # 1. Crear tabla bank_statements si no existe
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_statements (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id       TEXT NOT NULL DEFAULT 'default',
            source_type     TEXT NOT NULL,
            account_iban    TEXT NOT NULL,
            initial_balance DECIMAL(15, 2) NOT NULL,
            final_balance   DECIMAL(15, 2) NOT NULL,
            movements_sum   DECIMAL(15, 2) NOT NULL,
            is_balanced     INTEGER NOT NULL DEFAULT 1,
            file_checksum   TEXT,
            import_date     TEXT NOT NULL DEFAULT (datetime('now')),
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bank_statements_tenant_iban 
        ON bank_statements (tenant_id, account_iban)
    """)

    # 2. Verificar y ampliar columnas en bank_movements
    cols_info = cursor.execute("PRAGMA table_info(bank_movements)").fetchall()
    existing_cols = {c[1]: c[2] for c in cols_info} if cols_info else {}

    if not existing_cols:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bank_movements (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id             TEXT NOT NULL DEFAULT 'default',
                statement_id          INTEGER REFERENCES bank_statements(id),
                account_iban          TEXT,
                operation_date        TEXT NOT NULL,
                value_date            TEXT,
                amount                DECIMAL(15, 2) NOT NULL,
                balance_after         DECIMAL(15, 2) DEFAULT 0.00,
                concept               TEXT NOT NULL,
                reference             TEXT,
                reconciled_invoice_id INTEGER REFERENCES invoices(id),
                journal_entry_id      INTEGER REFERENCES legal_journal_entries(id),
                reconciliation_status TEXT NOT NULL DEFAULT 'UNRECONCILED',
                created_at            TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
    else:
        new_columns = {
            "tenant_id": "TEXT NOT NULL DEFAULT 'default'",
            "statement_id": "INTEGER REFERENCES bank_statements(id)",
            "account_iban": "TEXT",
            "operation_date": "TEXT",
            "value_date": "TEXT",
            "balance_after": "DECIMAL(15, 2) DEFAULT 0.00",
            "journal_entry_id": "INTEGER REFERENCES legal_journal_entries(id)",
            "reconciled_invoice_id": "INTEGER REFERENCES invoices(id)",
            "reconciliation_status": "TEXT NOT NULL DEFAULT 'UNRECONCILED'"
        }
        for col_name, col_def in new_columns.items():
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE bank_movements ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass

    # Índices adicionales de rendimiento
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_bank_movements_status 
        ON bank_movements (tenant_id, reconciliation_status)
    """)
    conn.commit()
