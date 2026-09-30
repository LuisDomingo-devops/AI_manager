"""
Test de Integración: Concurrencia masiva en SQLite con 30 hilos concurrentes
Feature: specs/020-sqlite-connection-pool-concurrency
Metodología: TDD Estricto conforme a la Constitución del proyecto
"""

import concurrent.futures
import random
import time
import pytest

from app.infrastructure.database.connection_manager import (
    _get_connection,
    write_transaction,
    reset_thread_local_pool,
)
from app.infrastructure.database.concurrency import retry_on_db_lock


@pytest.fixture(autouse=True)
def cleanup_pool():
    reset_thread_local_pool()
    yield
    reset_thread_local_pool()


def test_sqlite_30_threads_concurrent_reads_and_writes():
    """
    User Story 1 Acceptance Scenario:
    Ejecuta 30 hilos simultáneos realizando escrituras protegidas y lecturas concurrentes
    sobre la misma base de datos de tenant sin lanzar 'database is locked'.
    """
    tenant_id = "integration_concurrency_test"

    # Inicializar tabla de prueba
    with write_transaction(tenant_id) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS concurrency_log (id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id INT, val TEXT, created_at REAL)")

    total_threads = 30
    operations_per_thread = 10
    successful_writes = []
    successful_reads = []
    errors = []

    @retry_on_db_lock(max_retries=5, base_delay=0.02, max_delay=0.5)
    def perform_write(thread_idx: int, op_idx: int):
        with write_transaction(tenant_id) as conn:
            conn.execute(
                "INSERT INTO concurrency_log (thread_id, val, created_at) VALUES (?, ?, ?)",
                (thread_idx, f"payload_{thread_idx}_{op_idx}", time.time()),
            )

    @retry_on_db_lock(max_retries=5, base_delay=0.02, max_delay=0.5)
    def perform_read():
        conn = _get_connection(tenant_id)
        rows = conn.execute("SELECT COUNT(*) as cnt FROM concurrency_log").fetchone()
        return rows["cnt"]

    def worker(thread_idx: int):
        try:
            for op in range(operations_per_thread):
                if random.random() < 0.6:
                    perform_write(thread_idx, op)
                    successful_writes.append((thread_idx, op))
                else:
                    cnt = perform_read()
                    successful_reads.append(cnt)
                # Pequeño jitter
                time.sleep(random.uniform(0.001, 0.005))
        except Exception as e:
            errors.append(f"Thread-{thread_idx} error: {type(e).__name__}: {str(e)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=total_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(total_threads)]
        concurrent.futures.wait(futures)

    # Validaciones contractuales estrictas
    if errors:
        pytest.fail(f"Se produjeron {len(errors)} errores en la ejecución concurrente: {errors[:5]}")

    assert len(successful_writes) > 0, "Debe haber escrituras exitosas"
    assert len(successful_reads) > 0, "Debe haber lecturas exitosas"

    # Verificar que el conteo en BD coincide exactamente con las escrituras registradas
    conn_final = _get_connection(tenant_id)
    total_in_db = conn_final.execute("SELECT COUNT(*) as cnt FROM concurrency_log").fetchone()["cnt"]
    assert total_in_db == len(successful_writes), f"Discrepancia en registros: {total_in_db} en BD vs {len(successful_writes)} confirmadas"
