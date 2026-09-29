"""
Integration tests for complete migration execution and SQLite raw connection safety.
Verifica que toda la cadena de migraciones (000-023) se aplique sin fallos en conexiones
SQLite puras (sin row_factory) y sin violaciones de integridad referencial.
"""
import pytest
import sqlite3
from app.infrastructure.database.migrations import MigrationRunner

def test_migration_chain_on_raw_sqlite_connection():
    """
    Ejecuta todas las migraciones sobre una conexión SQLite pura sin sqlite3.Row.
    Garantiza que ninguna migración falle por acceso por clave string en tuplas ordinales.
    """
    conn = sqlite3.connect(":memory:")
    # Sin configurar conn.row_factory = sqlite3.Row
    applied = MigrationRunner.run_pending_migrations(conn)
    
    assert len(applied) >= 20, f"Se esperaban al menos 20 migraciones aplicadas, se obtuvieron: {len(applied)}"
    
    # Comprobar que schema_migrations tiene registradas las versiones
    applied_in_db = MigrationRunner.get_applied_migrations(conn)
    assert "000" in applied_in_db
    assert "014" in applied_in_db
    assert "023" in applied_in_db
    
    # Comprobar claves foráneas si el método está disponible
    if hasattr(MigrationRunner, "check_foreign_keys"):
        violations = MigrationRunner.check_foreign_keys(conn)
        assert violations == [], f"Se encontraron violaciones de integridad referencial: {violations}"
