import pytest
import sqlite3
from app.infrastructure.database.migrations import MigrationRunner
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection

def test_migration_005_upgrades_legacy_sif_event_log():
    """Prueba de integración: Simula una base de datos con esquema antiguo y aplica la migración 005."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # 1. Crear tabla con esquema heredado (anterior a la migración 005)
    conn.execute("""
        CREATE TABLE sif_event_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type    TEXT NOT NULL,
            timestamp     TEXT NOT NULL,
            payload       TEXT NOT NULL,
            event_hash    TEXT NOT NULL,
            previous_hash TEXT,
            signature     TEXT NOT NULL,
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    
    # Insertar un registro heredado
    conn.execute("""
        INSERT INTO sif_event_log (event_type, timestamp, payload, event_hash, previous_hash, signature)
        VALUES ('STARTUP_LEGACY', '2026-01-01T00:00:00', 'Arranque versión 1.0', 'HASH_LEGACY_001', NULL, 'SIG_LEGACY')
    """)
    conn.commit()

    # 2. Ejecutar las migraciones
    applied = MigrationRunner.run_pending_migrations(conn)
    assert "005" in applied or "005_fix_sif_event_log_schema" in str(applied)

    # 3. Comprobar que las columnas nuevas existen y los datos fueron migrados
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(sif_event_log)")
    cols = {row[1] for row in cursor.fetchall()}
    assert "current_hash" in cols
    assert "prev_event_hash" in cols
    assert "description" in cols

    row = conn.execute("SELECT * FROM sif_event_log WHERE id = 1").fetchone()
    assert row["current_hash"] == "HASH_LEGACY_001"
    assert row["description"] == "Arranque versión 1.0"
    conn.close()

def test_sif_event_lifecycle_startup_and_shutdown_integration():
    """Prueba de integración: Ciclo de vida completo de arranque y parada registrando eventos SIF sin errores."""
    VerifactuService.init_verifactu_schema()
    
    with _get_connection() as conn:
        conn.execute("DELETE FROM sif_event_log")
        conn.commit()

    # Evento de arranque
    h_start = VerifactuService.log_sif_event(
        event_type="STARTUP_SYSTEM",
        description="Inicio de integración SIF"
    )
    assert h_start is not None

    # Evento intermedio
    h_backup = VerifactuService.log_sif_event(
        event_type="BACKUP_EXPORT",
        description="Copia de seguridad realizada"
    )
    assert h_backup is not None

    # Evento de parada
    h_stop = VerifactuService.log_sif_event(
        event_type="SHUTDOWN_SYSTEM",
        description="Parada controlada del sistema SIF"
    )
    assert h_stop is not None

    # Verificar la cadena criptográfica
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM sif_event_log ORDER BY id ASC").fetchall()
        assert len(rows) == 3
        assert rows[0]["event_type"] == "STARTUP_SYSTEM"
        assert rows[0]["prev_event_hash"] is None
        assert rows[0]["current_hash"] == h_start

        assert rows[1]["event_type"] == "BACKUP_EXPORT"
        assert rows[1]["prev_event_hash"] == h_start
        assert rows[1]["current_hash"] == h_backup

        assert rows[2]["event_type"] == "SHUTDOWN_SYSTEM"
        assert rows[2]["prev_event_hash"] == h_backup
        assert rows[2]["current_hash"] == h_stop
