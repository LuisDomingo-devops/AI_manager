import pytest
import json
import sys
from app.domain.services.bank_service import BankService

@pytest.fixture(autouse=True)
def clean_db():
    from app.adapters.memory.memory import _get_connection
    with _get_connection() as conn:
        conn.execute("DELETE FROM bank_movements")
        conn.execute("DELETE FROM bank_connections")
        conn.commit()
    yield

def test_add_and_list_connections(clean_db):
    # Inicialmente no hay conexiones
    conns = BankService.list_connections()
    assert len(conns) == 0

    # Añadir una conexión
    conn_id = BankService.add_connection(
        alias="Mi Cuenta Santander",
        provider="mock",
        bank_name="Santander",
        iban="ES9100491500001234567890",
        credentials_json=json.dumps({"token": "xyz123"})
    )
    assert conn_id > 0

    # Listar conexiones
    conns = BankService.list_connections()
    assert len(conns) == 1
    assert conns[0]["alias"] == "Mi Cuenta Santander"
    assert conns[0]["bank_name"] == "Santander"
    assert conns[0]["iban"] == "ES9100491500001234567890"

def test_sync_connection(clean_db):
    conn_id = BankService.add_connection(
        alias="Cuenta Santander",
        provider="mock",
        bank_name="Santander",
        iban="ES9100491500001234567890",
        credentials_json=json.dumps({"account_id": "test_account"})
    )

    # Sincronizar movimientos
    count = BankService.sync_connection(conn_id)
    assert count == 2 # El mock provider devuelve 2 movimientos

    # Verificar reporte sin conciliar
    report = BankService.get_unreconciled_report(conn_id)
    assert len(report["movimientos_banco_pendientes"]) == 2
    assert report["movimientos_banco_pendientes"][0]["cuenta"] == "Cuenta Santander"

    # Segunda sincronización no debe duplicar movimientos
    count2 = BankService.sync_connection(conn_id)
    assert count2 == 0

def test_delete_connection(clean_db):
    conn_id = BankService.add_connection(
        alias="Santander Temporal",
        provider="mock",
        bank_name="Santander",
        iban="ES9100491500001234567890",
        credentials_json=json.dumps({"account_id": "test_account"})
    )
    
    # Sincronizar
    BankService.sync_connection(conn_id)
    
    # Eliminar conexión
    BankService.delete_connection(conn_id)
    
    conns = BankService.list_connections()
    assert len(conns) == 0
    
    # Los movimientos deben quedar huérfanos (connection_id = None) pero no borrados
    report = BankService.get_unreconciled_report(None)
    assert len(report["movimientos_banco_pendientes"]) == 2
    assert report["movimientos_banco_pendientes"][0]["cuenta"] == "Sin Vincular"
