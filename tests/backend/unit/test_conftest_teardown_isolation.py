"""
Test unitario para verificar el aislamiento y la limpieza en el teardown de conftest.
Feature: specs/021-sqlite-concurrency-isolation
User Story: US1 - Aislamiento limpio y predecible entre tests de la suite
"""

import pytest
from app.infrastructure.database import connection_manager
from tests.conftest import reset_db_caches


def test_teardown_resets_thread_local_pool_and_caches():
    """
    Verifica que el generador reset_db_caches en su fase de teardown (post-yield)
    cierra todas las conexiones del hilo y limpia los cachés y conexiones dummy.
    """
    # 1. Simular la fase de setup ejecutando hasta el yield
    gen = reset_db_caches.__wrapped__()
    next(gen)

    # 2. Abrir una conexión en el hilo actual simulando la ejecución del test
    conn = connection_manager._get_connection("tenant_teardown_test")
    conn.execute("CREATE TABLE IF NOT EXISTS test_teardown_table (id INT)")
    conn.execute("INSERT INTO test_teardown_table VALUES (1)")
    conn.commit()

    # Comprobar que en plena ejecución la conexión existe en el pool del hilo
    thread_conns = connection_manager._get_thread_connections()
    assert len(thread_conns) > 0, "Debe existir al menos una conexión en el pool del hilo"

    # 3. Ejecutar la fase de teardown (reanudar tras el yield)
    with pytest.raises(StopIteration):
        next(gen)

    # 4. Verificar que el teardown limpió completamente el pool thread-local
    cleaned_thread_conns = connection_manager._get_thread_connections()
    assert len(cleaned_thread_conns) == 0, (
        f"El teardown de reset_db_caches debe vaciar el pool thread-local, pero quedaron: {cleaned_thread_conns}"
    )

    # 5. Verificar que las conexiones dummy de test también fueron cerradas y vaciadas
    assert len(connection_manager._test_dummy_conns) == 0, (
        "El teardown de reset_db_caches debe vaciar _test_dummy_conns"
    )
