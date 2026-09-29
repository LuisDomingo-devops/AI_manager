"""
Suite QA de Gobernanza y Verificación de Proveedores Bancarios Falsos (Spec 003).
Audita exhaustivamente el catálogo de proveedores de BankProviderFactory para asegurar
que ningún proveedor enmascare fallos, devuelva transacciones ficticias en runtime,
o permita que datos simulados alcancen el libro mayor o los balances contables
(Contrato de Discovery - Sección 12: PROVEEDORES FALSOS).
"""
import pytest
import os
from app.infrastructure.adapters.bank_providers import (
    BankProviderFactory,
    GenericApiProvider,
    PlaidProvider,
    QontoProvider,
    TinkProvider,
    GoCardlessProvider,
    MockBankProvider,
)
from app.adapters.memory.memory import _get_connection

def test_qa_all_unimplemented_providers_raise_not_implemented():
    """
    Auditoría QA: Todo proveedor sin integración bancaria real debe
    rechazar explícitamente la descarga con NotImplementedError.
    """
    unimplemented_keys = ["generic", "plaid", "qonto"]
    for key in unimplemented_keys:
        provider = BankProviderFactory.get_provider(key)
        assert isinstance(provider, (GenericApiProvider, PlaidProvider, QontoProvider))
        with pytest.raises(NotImplementedError) as exc_info:
            provider.fetch_transactions({}, "acc_qa_01", "01/01/2026")
        assert len(str(exc_info.value)) > 0, f"El mensaje de error para '{key}' debe ser descriptivo."


def test_qa_real_providers_require_credentials_without_inventing_data():
    """
    Auditoría QA: Los proveedores reales no deben inventar movimientos de relleno
    cuando las credenciales no son suministradas o son inválidas.
    """
    real_providers_requiring_creds = ["gocardless", "tink"]
    for key in real_providers_requiring_creds:
        provider = BankProviderFactory.get_provider(key)
        with pytest.raises(ValueError) as exc_info:
            provider.fetch_transactions({}, "acc_qa_01", "01/01/2026")
        error_msg = str(exc_info.value).lower()
        assert "credenciales" in error_msg or "configuradas" in error_msg, (
            f"El proveedor {key} debe requerir credenciales explícitamente."
        )


def test_qa_mock_bank_provider_isolated_from_production(monkeypatch):
    """
    Auditoría QA: MockBankProvider debe estar terminantemente bloqueado
    cuando el entorno sea de producción (ENV=production).
    """
    monkeypatch.setenv("ENV", "production")
    with pytest.raises(NotImplementedError) as exc_info:
        BankProviderFactory.get_provider("mock")
    assert "no permitido en entorno de producción" in str(exc_info.value)


def test_qa_database_never_polluted_by_fake_transactions():
    """
    Auditoría QA: Comprobar que las tablas de movimientos contables y bancarios
    permanecen con 0 movimientos ante intentos de consulta en proveedores vacíos.
    """
    with _get_connection() as conn:
        before_count = conn.execute("SELECT COUNT(*) as c FROM bank_movements").fetchone()["c"]

    providers_to_test = ["generic", "plaid", "qonto", "gocardless", "tink"]
    for p_name in providers_to_test:
        prov = BankProviderFactory.get_provider(p_name)
        try:
            prov.fetch_transactions({}, "qa_acc", "01/01/2026")
        except (NotImplementedError, ValueError):
            pass  # Excepción esperada por contrato

    with _get_connection() as conn:
        after_count = conn.execute("SELECT COUNT(*) as c FROM bank_movements").fetchone()["c"]
        assert after_count == before_count, "No debe haberse insertado ninguna transacción ficticia en la BD."
