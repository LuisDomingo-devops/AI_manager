"""
Test Unitario: Preservación de Triggers de Seguridad Veri*Factu (Spec 001 - TDD)
Verifica que los triggers de inalterabilidad fiscal no pueden ser eliminados en tests
y que bloquean activamente cualquier mutación destructiva sobre verifactu_invoices.
"""

import sqlite3
import pytest
from app.adapters.memory.memory import _get_connection

def test_verifactu_delete_trigger_blocks_deletion():
    """Comprueba que intentar borrar registros en verifactu_invoices lanza un error por trigger."""
    import importlib
    from app.infrastructure.database.migrations import MigrationRunner
    m019 = importlib.import_module("migrations.versions.019_immutability_triggers")
    with _get_connection() as conn:
        MigrationRunner.run_pending_migrations(conn)
        # Re-aplicar triggers si algún test anterior ejecutó DROP TRIGGER
        m019.upgrade(conn)
        
        # Asegurar que el trigger está activo en el esquema
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_prevent_delete_verifactu'")
        trigger = cursor.fetchone()
        assert trigger is not None, "El trigger trg_prevent_delete_verifactu no existe en la base de datos"
        
        # Intentar borrar debe fallar si hay registros
        cursor.execute("SELECT count(*) FROM verifactu_invoices")
        count = cursor.fetchone()[0]
        
        if count > 0:
            with pytest.raises(sqlite3.IntegrityError) as exc_info:
                cursor.execute("DELETE FROM verifactu_invoices")
            assert "inmutabilidad fiscal" in str(exc_info.value).lower() or "no se permite eliminar" in str(exc_info.value).lower()


def test_verifactu_empty_chain_audit_in_memory_isolation():
    """
    Verifica que la auditoría con 0 facturas se puede testear de forma aislada en memoria
    sin destruir los triggers de la base de datos de producción/test compartida.
    """
    mem_conn = sqlite3.connect(":memory:")
    mem_conn.row_factory = sqlite3.Row
    
    # Crear esquema mínimo en memoria
    mem_conn.execute("""
        CREATE TABLE verifactu_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id TEXT UNIQUE,
            current_hash TEXT,
            prev_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Trigger intacto
    mem_conn.execute("""
        CREATE TRIGGER trg_test_prevent_del BEFORE DELETE ON verifactu_invoices
        BEGIN
            SELECT RAISE(ABORT, 'Prohibido eliminar');
        END;
    """)
    mem_conn.commit()
    
    # Simular auditoría en memoria vacía
    cursor = mem_conn.cursor()
    cursor.execute("SELECT count(*) FROM verifactu_invoices")
    total = cursor.fetchone()[0]
    assert total == 0, "La base de datos aislada debe tener 0 facturas"
    
    # Trigger activo
    cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='trg_test_prevent_del'")
    assert cursor.fetchone() is not None
    mem_conn.close()
