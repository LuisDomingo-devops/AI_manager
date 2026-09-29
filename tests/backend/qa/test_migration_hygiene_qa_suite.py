"""
QA Suite: Database Migration Hygiene and Schema Integrity Audit.
Audita exhaustivamente el catálogo de migraciones conforme al Contrato de Discovery § 18 y § 31.12:
- Cero duplicados de versión
- Descripciones descriptivas
- Idempotencia estricta en ejecuciones sucesivas
- Cero violaciones de claves foráneas
"""
import pytest
import sqlite3
from app.infrastructure.database.migrations import MigrationRunner

def test_qa_migration_catalog_uniqueness_and_completeness():
    """Auditoría QA: El catálogo de migraciones no debe contener versiones duplicadas y debe tener descripciones válidas."""
    migrations = MigrationRunner.load_available_migrations()
    versions = [m.version for m in migrations]
    
    # 1. Unicidad
    assert len(versions) == len(set(versions)), f"Se detectaron versiones duplicadas: {versions}"
    
    # 2. Descripciones
    for m in migrations:
        assert m.description is not None, f"Migración {m.version} no tiene descripción"
        assert len(m.description.strip()) >= 5, (
            f"Migración {m.version} tiene descripción demasiado corta o inválida: '{m.description}'"
        )

def test_qa_migration_idempotence_and_stability():
    """Auditoría QA: Múltiples ejecuciones del runner en la misma base de datos deben ser inocuas."""
    conn = sqlite3.connect(":memory:")
    
    # Primera ejecución: aplica todas
    first_run = MigrationRunner.run_pending_migrations(conn)
    assert len(first_run) >= 20, f"Primera ejecución aplicó menos de 20 migraciones: {len(first_run)}"
    
    # Segunda ejecución: no aplica nada
    second_run = MigrationRunner.run_pending_migrations(conn)
    assert second_run == [], f"Segunda ejecución no debe aplicar migraciones: {second_run}"
    
    # Tercera ejecución: no aplica nada
    third_run = MigrationRunner.run_pending_migrations(conn)
    assert third_run == [], f"Tercera ejecución no debe aplicar migraciones: {third_run}"

def test_qa_database_referential_integrity():
    """Auditoría QA: La base de datos resultante no debe contener violaciones de claves foráneas."""
    conn = sqlite3.connect(":memory:")
    MigrationRunner.run_pending_migrations(conn)
    
    violations = MigrationRunner.check_foreign_keys(conn)
    assert violations == [], f"Violaciones de clave foránea detectadas en esquema migrado: {violations}"
