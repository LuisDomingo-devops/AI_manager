"""
test_migrations.py
==================
Suite de tests TDD para verificar la integridad del sistema de migraciones SQL.

Cubre:
  1. Migracion desde cero (fresh DB)
  2. Idempotencia (ejecutar runner dos veces es inocuo)
  3. Orden secuencial de versiones
  4. Presencia de tablas criticas y columnas clave
  5. Tablas de servicios (011-013) incluidas en el runner
"""
import sqlite3
import pytest
import os
import tempfile
from app.infrastructure.database.migrations import MigrationRunner
from app.infrastructure.database.connection_manager import init_all_schemas


def _make_fresh_conn() -> sqlite3.Connection:
    """Crea una conexion SQLite en memoria limpia para tests aislados."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


# --- TESTS UNITARIOS --------------------------------------------------------

def test_migration_runner_loads_versions():
    """MigrationRunner carga correctamente los archivos de versiones."""
    migrations = MigrationRunner.load_available_migrations()
    versions = [m.version for m in migrations]
    # Debe haber al menos las versiones 000 a 013
    assert "000" in versions
    assert "001" in versions
    assert "011" in versions
    assert "012" in versions
    assert "013" in versions


def test_migrations_sorted_by_version():
    """Las migraciones se cargan en orden ascendente."""
    migrations = MigrationRunner.load_available_migrations()
    versions = [m.version for m in migrations]
    assert versions == sorted(versions), f"Versiones desordenadas: {versions}"


def test_migration_runner_creates_schema_migrations_table():
    """MigrationRunner crea la tabla schema_migrations si no existe."""
    conn = _make_fresh_conn()
    MigrationRunner.init_migrations_table(conn)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'")
    assert cursor.fetchone() is not None


# --- TESTS DE INTEGRACION ----------------------------------------------------

def test_fresh_db_applies_all_migrations():
    """
    Una BD nueva con init_all_schemas() tiene todas las tablas criticas
    y schema_migrations registra todas las versiones.
    """
    conn = _make_fresh_conn()
    init_all_schemas(conn)

    cursor = conn.cursor()

    # Comprobar tablas del schema core/billing/accounting
    tables_to_check = [
        "invoices", "quotes", "products", "payments", "invoice_items", "quote_items",
        "pgc_accounts", "journal_entries", "ledger_entries", "fiscal_year_status",
        "bank_connections", "bank_movements", "bank_transfers", "subscription_status",
        "user_profile", "contacts", "assets", "projects",
        "schema_migrations",
    ]
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    for table in tables_to_check:
        assert table in existing_tables, f"Tabla critica faltante: {table}"


def test_fresh_db_has_service_tables():
    """
    Una BD nueva tiene las tablas de servicios de dominio (011-013).
    """
    conn = _make_fresh_conn()
    init_all_schemas(conn)

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}

    service_tables = [
        "employees", "payrolls", "settlements", "tgss_afi_records",  # 011
        "verifactu_invoices", "sif_event_log",                         # 012
        "audit_ledger_log", "llm_metrics_log", "user_sessions",        # 013
    ]
    for table in service_tables:
        assert table in existing_tables, f"Tabla de servicio faltante: {table}"


def test_migrations_are_idempotent():
    """
    Ejecutar run_pending_migrations dos veces no falla ni duplica registros.
    """
    conn = _make_fresh_conn()
    init_all_schemas(conn)

    # Segunda ejecucion del runner no debe lanzar excepciones
    applied_second_run = MigrationRunner.run_pending_migrations(conn)
    assert applied_second_run == [], "Segunda ejecucion no deberia aplicar migraciones nuevas"


def test_all_migration_versions_recorded():
    """
    Despues de init_all_schemas, schema_migrations contiene al menos las versiones 000-010.
    """
    conn = _make_fresh_conn()
    init_all_schemas(conn)

    applied = MigrationRunner.get_applied_migrations(conn)
    for version in ["000", "001", "002", "003", "004", "005", "006", "007", "008", "009", "010"]:
        assert version in applied, f"Version {version} no registrada en schema_migrations"


def test_invoices_critical_columns():
    """
    La tabla invoices tiene todas las columnas criticas (incluyendo las anyadidas
    despues de la version 001 original).
    """
    conn = _make_fresh_conn()
    init_all_schemas(conn)

    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(invoices)")
    cols = {row["name"] for row in cursor.fetchall()}

    critical_cols = [
        "id", "invoice_id", "date", "issuer_name", "issuer_nif",
        "total_amount", "status", "blind_index", "created_at",
        "contact_id", "tax_engine_version", "requires_manual_confirmation",
    ]
    for col in critical_cols:
        assert col in cols, f"Columna critica faltante en invoices: {col}"


# --- TEST QA ----------------------------------------------------------------

def test_migration_version_uniqueness():
    """No hay versiones duplicadas en el conjunto de migraciones disponibles."""
    migrations = MigrationRunner.load_available_migrations()
    versions = [m.version for m in migrations]
    assert len(versions) == len(set(versions)), f"Versiones duplicadas detectadas: {versions}"


def test_all_migrations_have_descriptions():
    """Todas las migraciones tienen description no vacia."""
    migrations = MigrationRunner.load_available_migrations()
    for m in migrations:
        assert m.description and len(m.description) > 5, \
            f"Migracion {m.version} sin descripcion valida: '{m.description}'"
