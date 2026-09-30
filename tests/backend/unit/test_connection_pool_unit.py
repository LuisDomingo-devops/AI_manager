"""
Tests Unitarios: Pool de Conexiones SQLite, TenantLockRegistry y RetryPolicy
Feature: specs/020-sqlite-connection-pool-concurrency
Metodología: TDD Estricto conforme a la Constitución del proyecto
"""

import sqlite3
import threading
import time
import pytest
from unittest.mock import MagicMock

from app.infrastructure.database.concurrency import (
    TenantLockRegistry,
    retry_on_db_lock,
    RetryPolicy,
)
from app.infrastructure.database.connection_manager import (
    _get_connection,
    write_transaction,
    reset_thread_local_pool,
    DEFAULT_BUSY_TIMEOUT_MS,
    SQLITE_PRAGMAS,
)


class TestTenantLockRegistry:
    def test_reentrant_lock_same_thread(self):
        """Verifica que el cerrojo de un tenant es reentrante (RLock) en el mismo hilo."""
        registry = TenantLockRegistry()
        lock = registry.get_lock("tenant_a")
        
        # Debe poder adquirirse múltiples veces en el mismo hilo sin bloquearse
        acquired_1 = lock.acquire(timeout=0.1)
        acquired_2 = lock.acquire(timeout=0.1)
        assert acquired_1 is True
        assert acquired_2 is True
        
        lock.release()
        lock.release()

    def test_mutual_exclusion_different_threads_same_tenant(self):
        """Verifica exclusión mutua entre dos hilos para el mismo tenant."""
        registry = TenantLockRegistry()
        tenant = "tenant_a"
        lock = registry.get_lock(tenant)
        
        acquired_by_thread_2 = []
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            # Intenta adquirir el lock con timeout corto
            success = registry.get_lock(tenant).acquire(timeout=0.05)
            if success:
                acquired_by_thread_2.append(True)
                registry.get_lock(tenant).release()
            else:
                acquired_by_thread_2.append(False)

        # Hilo 1 adquiere el lock
        assert lock.acquire(timeout=0.1) is True
        t2 = threading.Thread(target=worker)
        t2.start()
        
        barrier.wait()
        t2.join()
        lock.release()

        assert acquired_by_thread_2 == [False], "El hilo 2 no debió poder adquirir el lock del mismo tenant"

    def test_independent_locks_different_tenants(self):
        """Verifica que dos tenants diferentes tienen cerrojos independientes."""
        registry = TenantLockRegistry()
        lock_a = registry.get_lock("tenant_a")
        lock_b = registry.get_lock("tenant_b")

        assert lock_a is not lock_b
        assert lock_a.acquire(timeout=0.1) is True
        assert lock_b.acquire(timeout=0.1) is True

        lock_a.release()
        lock_b.release()


class TestRetryOnDbLock:
    def test_retry_success_after_transient_lock(self):
        """Verifica que la función se reintenta y tiene éxito si el bloqueo se libera."""
        call_count = 0

        @retry_on_db_lock(max_retries=3, base_delay=0.01, max_delay=0.05)
        def unstable_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise sqlite3.OperationalError("database is locked")
            return "SUCCESS"

        result = unstable_operation()
        assert result == "SUCCESS"
        assert call_count == 3

    def test_retry_exhaustion_raises_operational_error(self):
        """Verifica que tras agotar los reintentos se propaga la excepción original."""
        call_count = 0

        @retry_on_db_lock(max_retries=3, base_delay=0.01, max_delay=0.05)
        def perpetually_locked():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("database table is locked: conversation_metadata")

        with pytest.raises(sqlite3.OperationalError) as exc_info:
            perpetually_locked()

        assert "database table is locked" in str(exc_info.value)
        assert call_count == 4  # Intento inicial + 3 reintentos

    def test_no_retry_on_unrelated_exception(self):
        """Verifica que excepciones distintas a bloqueo de BD no se reintentan."""
        call_count = 0

        @retry_on_db_lock(max_retries=3, base_delay=0.01)
        def raises_syntax_error():
            nonlocal call_count
            call_count += 1
            raise sqlite3.OperationalError("near 'SYNTAX': syntax error")

        with pytest.raises(sqlite3.OperationalError) as exc_info:
            raises_syntax_error()

        assert "syntax error" in str(exc_info.value)
        assert call_count == 1  # No reintenta errores de sintaxis


class TestConnectionPoolAndTransactions:
    def setup_method(self):
        reset_thread_local_pool()

    def teardown_method(self):
        reset_thread_local_pool()

    def test_pragmas_configured_correctly(self):
        """Verifica que las constantes y pragmas de SQLite están configurados."""
        assert DEFAULT_BUSY_TIMEOUT_MS == 60000
        pragmas_str = " ".join(SQLITE_PRAGMAS)
        assert "busy_timeout = 60000" in pragmas_str or "busy_timeout=60000" in pragmas_str
        assert "synchronous = NORMAL" in pragmas_str or "synchronous=NORMAL" in pragmas_str

    def test_thread_local_affinity_same_thread(self):
        """Verifica que llamadas sucesivas en el mismo hilo retornan la misma conexión."""
        conn1 = _get_connection("tenant_pool_test")
        conn2 = _get_connection("tenant_pool_test")
        assert conn1 is conn2, "Llamadas en el mismo hilo deben reutilizar la conexión"

    def test_thread_local_affinity_different_threads(self):
        """Verifica que distintos hilos obtienen conexiones distintas."""
        conns = []

        def worker():
            c = _get_connection("tenant_pool_test")
            conns.append(c)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(conns) == 2
        assert conns[0] is not conns[1], "Hilos distintos deben tener conexiones separadas"

    def test_write_transaction_commit_on_success(self):
        """Verifica que write_transaction realiza commit automático sin error."""
        with write_transaction("tenant_tx_test") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test_tx (id INTEGER PRIMARY KEY, val TEXT)")
            conn.execute("INSERT INTO test_tx (val) VALUES ('committed')")

        # Verificar en una nueva lectura
        conn_read = _get_connection("tenant_tx_test")
        row = conn_read.execute("SELECT val FROM test_tx WHERE val = 'committed'").fetchone()
        assert row is not None
        assert row["val"] == "committed"

    def test_write_transaction_rollback_on_exception(self):
        """Verifica que write_transaction ejecuta rollback automático si ocurre una excepción."""
        with write_transaction("tenant_tx_test2") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test_tx2 (id INTEGER PRIMARY KEY, val TEXT)")

        with pytest.raises(RuntimeError):
            with write_transaction("tenant_tx_test2") as conn:
                conn.execute("INSERT INTO test_tx2 (val) VALUES ('rolled_back')")
                raise RuntimeError("Simulated failure")

        conn_read = _get_connection("tenant_tx_test2")
        row = conn_read.execute("SELECT val FROM test_tx2 WHERE val = 'rolled_back'").fetchone()
        assert row is None, "La transacción fallida debió revertirse con rollback"

    def test_readonly_connection_blocks_mutations(self):
        """Verifica que get_readonly_connection impide operaciones de mutación (query_only = ON)."""
        from app.infrastructure.database.connection_manager import get_readonly_connection
        with write_transaction("tenant_ro_test") as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS test_ro (id INTEGER PRIMARY KEY, val TEXT)")
            conn.execute("INSERT INTO test_ro (val) VALUES ('read_data')")

        ro_conn = get_readonly_connection("tenant_ro_test")
        row = ro_conn.execute("SELECT val FROM test_ro WHERE val = 'read_data'").fetchone()
        assert row is not None
        assert row["val"] == "read_data"

        # Intentar escribir sobre conexión de solo lectura debe fallar
        with pytest.raises(sqlite3.OperationalError) as exc_info:
            ro_conn.execute("INSERT INTO test_ro (val) VALUES ('unauthorized_write')")
        assert "readonly" in str(exc_info.value).lower() or "read-only" in str(exc_info.value).lower()
