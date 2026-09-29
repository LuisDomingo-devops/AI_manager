"""
Tests de Integración de Integridad de Sincronización Bancaria (Spec 003).
Verifica que BankService.sync_connection rechaza sincronizar proveedores no implementados
o sin credenciales válidas, garantizando que nunca se inserten datos ficticios en bank_movements.
"""
import pytest
import json
from app.domain.services.bank_service import BankService
from app.adapters.memory.memory import _get_connection

@pytest.fixture(autouse=True)
def clean_bank_db():
    with _get_connection() as conn:
        conn.execute("DELETE FROM bank_movements")
        conn.execute("DELETE FROM bank_connections")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM bank_movements")
        conn.execute("DELETE FROM bank_connections")
        conn.commit()


def test_sync_generic_provider_rejects_and_no_movements_inserted():
    """Sincronizar una conexión 'generic' debe lanzar NotImplementedError y no insertar movimientos."""
    conn_id = BankService.add_connection(
        alias="Cuenta Genérica Test",
        provider="generic",
        bank_name="Generic Bank",
        iban="ES0000000000000000000000",
        credentials_json=json.dumps({"api_url": "https://api.example.com", "api_token": "token123"})
    )
    with pytest.raises(NotImplementedError):
        BankService.sync_connection(conn_id)

    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM bank_movements WHERE connection_id = ?", (conn_id,)).fetchone()["c"]
        assert count == 0


def test_sync_plaid_provider_rejects_and_no_movements_inserted():
    """Sincronizar una conexión 'plaid' debe lanzar NotImplementedError y no insertar movimientos."""
    conn_id = BankService.add_connection(
        alias="Cuenta Plaid Test",
        provider="plaid",
        bank_name="Plaid Gateway",
        iban="ES1111111111111111111111",
        credentials_json=json.dumps({"client_id": "plaid_id", "secret": "plaid_sec"})
    )
    with pytest.raises(NotImplementedError):
        BankService.sync_connection(conn_id)

    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM bank_movements WHERE connection_id = ?", (conn_id,)).fetchone()["c"]
        assert count == 0


def test_sync_qonto_provider_rejects_and_no_movements_inserted():
    """Sincronizar una conexión 'qonto' debe lanzar NotImplementedError y no insertar movimientos."""
    conn_id = BankService.add_connection(
        alias="Cuenta Qonto Test",
        provider="qonto",
        bank_name="Qonto Bank",
        iban="ES2222222222222222222222",
        credentials_json=json.dumps({"secret_key": "qonto_sec", "organization_slug": "my_org"})
    )
    with pytest.raises(NotImplementedError):
        BankService.sync_connection(conn_id)

    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM bank_movements WHERE connection_id = ?", (conn_id,)).fetchone()["c"]
        assert count == 0


def test_sync_tink_without_credentials_rejects_and_no_movements_inserted():
    """Sincronizar una conexión 'tink' sin credenciales válidas debe lanzar ValueError y no insertar movimientos."""
    conn_id = BankService.add_connection(
        alias="Cuenta Tink Test",
        provider="tink",
        bank_name="ABANCA",
        iban="ES3333333333333333333333",
        credentials_json=json.dumps({})
    )
    with pytest.raises(ValueError):
        BankService.sync_connection(conn_id)

    with _get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM bank_movements WHERE connection_id = ?", (conn_id,)).fetchone()["c"]
        assert count == 0
