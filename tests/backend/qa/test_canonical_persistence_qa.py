import threading
import pytest
from app.infrastructure.database.connection_manager import (
    _get_connection,
    get_readonly_connection,
    write_transaction,
    tenant_context
)

def test_canonical_persistence_transactions_and_isolation_qa():
    """QA de regresión para operaciones transaccionales y aislamiento multi-tenant en infraestructura canónica."""
    tenant_a = "tenant_qa_alpha"
    tenant_b = "tenant_qa_beta"

    prev = tenant_context.get()
    try:
        # 1. Escritura en tenant A
        tenant_context.set(tenant_a)
        with write_transaction() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('qa_key', 'alpha_value')")

        # 2. Escritura en tenant B
        tenant_context.set(tenant_b)
        with write_transaction() as conn:
            conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('qa_key', 'beta_value')")

        # 3. Comprobar aislamiento de lectura
        tenant_context.set(tenant_a)
        ro_conn = get_readonly_connection()
        cursor = ro_conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'qa_key'")
        row_a = cursor.fetchone()
        assert row_a is not None
        assert row_a["value"] == "alpha_value"

        tenant_context.set(tenant_b)
        ro_conn_b = get_readonly_connection()
        cursor_b = ro_conn_b.cursor()
        cursor_b.execute("SELECT value FROM settings WHERE key = 'qa_key'")
        row_b = cursor_b.fetchone()
        assert row_b is not None
        assert row_b["value"] == "beta_value"
    finally:
        tenant_context.set(prev)
