import sqlite3
import json
import logging
from pathlib import Path
import pytest

from app.infrastructure.database.migrations import MigrationRunner
from app.utils.logger import JSONFormatter, build_logger, LOG_DIR

def test_migrations_runner_lifecycle():
    """
    Verifica el ciclo de vida completo del motor de migraciones:
    - Inicialización de tabla de control
    - Carga y ejecución secuencial de versiones
    - Idempotencia (no repite migraciones ya aplicadas)
    - Creación efectiva de las tablas de negocio
    """
    conn = sqlite3.connect(":memory:")
    
    # 1. Ejecutar migraciones pendientes por primera vez
    applied_first = MigrationRunner.run_pending_migrations(conn)
    assert "001" in applied_first
    assert "002" in applied_first
    assert "003" in applied_first

    # 2. Verificar que se registraron en schema_migrations
    applied_in_db = MigrationRunner.get_applied_migrations(conn)
    assert set(applied_in_db) == {"001", "002", "003"}

    # 3. Idempotencia: segunda ejecución consecutiva no debe reaplicar nada
    applied_second = MigrationRunner.run_pending_migrations(conn)
    assert applied_second == []

    # 4. Verificar que las tablas existen y son operativas
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    assert "conversations" in tables
    assert "invoices" in tables
    assert "pgc_accounts" in tables
    assert "verifactu_invoices" in tables
    assert "sif_event_log" in tables
    assert "fiscal_year_status" in tables
    assert "b2b_invoice_status_history" in tables

    conn.close()


def test_json_structured_logging():
    """
    Verifica que el formateador de logs JSON estructurados emita JSON canónico (RFC 8259)
    con metadatos enriquecidos para observabilidad empresarial.
    """
    formatter = JSONFormatter()
    
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=42,
        msg="Operación contable completada exitosamente",
        args=(),
        exc_info=None
    )
    record.request_id = "REQ-AUDIT-999"

    formatted_json = formatter.format(record)
    
    # Validar que es JSON parseable y tiene los campos clave
    data = json.loads(formatted_json)
    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Operación contable completada exitosamente"
    assert data["request_id"] == "REQ-AUDIT-999"
    assert data["tenant_id"] is not None
    assert "timestamp" in data
    assert data["line"] == 42


def test_docker_and_ci_files_exist():
    """
    Verifica que los artefactos de infraestructura, CI/CD y despliegue existan y contengan directivas clave.
    """
    root_dir = Path(__file__).resolve().parents[1]
    
    dockerfile = root_dir / "Dockerfile"
    docker_compose = root_dir / "docker-compose.yml"
    ci_workflow = root_dir / ".github" / "workflows" / "ci.yml"

    assert dockerfile.exists()
    assert "FROM python:3.12-slim" in dockerfile.read_text(encoding="utf-8")
    assert "USER appuser" in dockerfile.read_text(encoding="utf-8")

    assert docker_compose.exists()
    assert "alfonso-core" in docker_compose.read_text(encoding="utf-8")

    assert ci_workflow.exists()
    assert "compliance-and-tests" in ci_workflow.read_text(encoding="utf-8")
