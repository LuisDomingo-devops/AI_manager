"""
Test de Integración: Aislamiento entre Lectores y Escritores (User Story 3)
Feature: specs/020-sqlite-connection-pool-concurrency
Metodología: TDD Estricto conforme a la Constitución del proyecto
"""

import concurrent.futures
import time
import pytest

from app.infrastructure.database.connection_manager import (
    _get_connection,
    get_readonly_connection,
    write_transaction,
    reset_thread_local_pool,
)
from app.infrastructure.database.concurrency import retry_on_db_lock


def test_concurrent_analytical_reads_do_not_block_writes():
    """
    Verifica que consultas analíticas pesadas (sumas y saldos, balances)
    usando get_readonly_connection se ejecutan en paralelo con transacciones de escritura
    sin bloquearse mutuamente.
    """
    tenant_id = "isolation_tenant"

    # Preparar el esquema y datos iniciales asegurando que la conexión permanezca abierta
    main_conn = _get_connection(tenant_id)
    with write_transaction(tenant_id) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ledger_mock (id INTEGER PRIMARY KEY AUTOINCREMENT, account TEXT, debit REAL, credit REAL)")
        conn.execute("DELETE FROM ledger_mock")
        for i in range(200):
            conn.execute("INSERT INTO ledger_mock (account, debit, credit) VALUES (?, ?, ?)", (f"430{i % 10}", 100.0 + i, 0.0))

    analytical_results = []
    write_results = []
    errors = []

    @retry_on_db_lock(max_retries=10, base_delay=0.02, max_delay=0.2)
    def do_read(ro_conn):
        return ro_conn.execute("SELECT COUNT(*) as cnt, SUM(debit) as total_debit FROM ledger_mock").fetchone()

    def long_analytical_reader(reader_id: int):
        try:
            ro_conn = get_readonly_connection(tenant_id)
            for _ in range(5):
                row = do_read(ro_conn)
                analytical_results.append((reader_id, row["cnt"], row["total_debit"]))
                time.sleep(0.005)
        except Exception as e:
            errors.append(f"Reader-{reader_id} error: {type(e).__name__}: {str(e)}")

    @retry_on_db_lock(max_retries=10, base_delay=0.02, max_delay=0.2)
    def do_write(writer_id: int):
        with write_transaction(tenant_id) as conn:
            conn.execute("INSERT INTO ledger_mock (account, debit, credit) VALUES (?, ?, ?)", (f"700{writer_id}", 50.0, 0.0))

    def continuous_writer(writer_id: int):
        try:
            for j in range(10):
                do_write(writer_id)
                write_results.append((writer_id, j))
                time.sleep(0.005)
        except Exception as e:
            errors.append(f"Writer-{writer_id} error: {type(e).__name__}: {str(e)}")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        readers = [executor.submit(long_analytical_reader, i) for i in range(4)]
        writers = [executor.submit(continuous_writer, i) for i in range(4)]
        concurrent.futures.wait(readers + writers)

    if errors:
        pytest.fail(f"Errores de interferencia entre lectores y escritores: {errors[:5]}")

    assert len(analytical_results) == 20, f"Lecturas esperadas: 20, obtenidas: {len(analytical_results)}"
    assert len(write_results) == 40, f"Escrituras esperadas: 40, obtenidas: {len(write_results)}"
