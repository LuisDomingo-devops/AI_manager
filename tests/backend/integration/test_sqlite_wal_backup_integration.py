"""
Test de Integración para Backup y Restauración Nativa SQLite WAL (User Story 6).
Valida que BackupService use conn.backup() para generar copias en caliente consistentes sin corrupción.
"""

import os
import sqlite3
import tempfile
import pytest
from app.infrastructure.database.backup_service import BackupService


def test_sqlite_wal_backup_and_restore():
    """Valida backup atómico en caliente mediante sqlite3.Connection.backup()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src_db_path = os.path.join(tmpdir, "source.db")
        dst_db_path = os.path.join(tmpdir, "backup.db")
        
        # 1. Crear base de datos de origen en modo WAL y llenarla de datos
        src_conn = sqlite3.connect(src_db_path)
        src_conn.execute("PRAGMA journal_mode = WAL;")
        src_conn.execute("CREATE TABLE test_data (id INTEGER PRIMARY KEY, name TEXT);")
        for i in range(100):
            src_conn.execute("INSERT INTO test_data (name) VALUES (?);", (f"Registro {i}",))
        src_conn.commit()
        
        # 2. Ejecutar backup usando BackupService
        service = BackupService()
        backup_file = service.create_backup(source_conn=src_conn, destination_path=dst_db_path)
        assert os.path.exists(backup_file)
        assert os.path.getsize(backup_file) > 0
        src_conn.close()
        
        # 3. Validar integridad en la base de datos de backup
        dst_conn = sqlite3.connect(dst_db_path)
        cursor = dst_conn.cursor()
        cursor.execute("SELECT count(*) FROM test_data;")
        count = cursor.fetchone()[0]
        assert count == 100
        
        # Comprobar que no hay corrupción de esquema
        cursor.execute("PRAGMA integrity_check;")
        check_result = cursor.fetchone()[0]
        assert check_result == "ok"
        dst_conn.close()
