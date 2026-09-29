"""
Unit tests for MigrationRunner hygiene and metadata extraction.
Verifica que MigrationRunner normalice metadatos mayúsculas/minúsculas
y proporcione verificación de claves foráneas.
"""
import pytest
import sqlite3
from app.infrastructure.database.migrations import MigrationRunner

def test_migration_runner_extracts_lowercase_metadata():
    """
    Verifica que MigrationRunner extraiga 'version' y 'description' en minúsculas
    si el módulo no define las constantes en mayúsculas (ej: migración 014).
    """
    migrations = MigrationRunner.load_available_migrations()
    mig_014 = next((m for m in migrations if m.version == "014"), None)
    
    assert mig_014 is not None, "La migración 014 debe estar cargada"
    assert "bcrypt" in mig_014.description.lower(), (
        f"La descripción de la migración 014 debe provenir del atributo 'description' ('{mig_014.description}'), no del fallback file.stem"
    )

def test_migration_runner_has_check_foreign_keys():
    """
    Verifica que MigrationRunner proporcione un método check_foreign_keys(conn)
    para auditar la integridad referencial.
    """
    assert hasattr(MigrationRunner, "check_foreign_keys"), (
        "MigrationRunner debe implementar el método check_foreign_keys(conn)"
    )
    conn = sqlite3.connect(":memory:")
    violations = MigrationRunner.check_foreign_keys(conn)
    assert violations == [], f"Una BD vacía no debe tener violaciones de FK: {violations}"
