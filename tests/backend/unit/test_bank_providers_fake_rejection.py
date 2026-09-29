"""
Tests Unitarios de Rechazo de Proveedores Bancarios Ficticios (Spec 003).
Verifica que los adaptadores sin integración real no devuelvan datos inventados
y lancen NotImplementedError o ValueError según el Contrato de Discovery (Sección 12).
"""
import pytest
from app.infrastructure.adapters.bank_providers import (
    GenericApiProvider,
    PlaidProvider,
    QontoProvider,
    TinkProvider,
)

def test_generic_api_provider_raises_not_implemented():
    """GenericApiProvider no tiene API real y debe lanzar NotImplementedError."""
    provider = GenericApiProvider()
    with pytest.raises(NotImplementedError) as exc_info:
        provider.fetch_transactions({}, "generic_acc_01", "01/01/2026")
    assert "no tiene integración" in str(exc_info.value) or "no implementada" in str(exc_info.value)

    with pytest.raises(NotImplementedError):
        provider.get_auth_link("http://localhost:8000/cb", {})

    with pytest.raises(NotImplementedError):
        provider.confirm_auth("req_123", {})


def test_plaid_provider_raises_not_implemented():
    """PlaidProvider no tiene implementación real y debe lanzar NotImplementedError."""
    provider = PlaidProvider()
    with pytest.raises(NotImplementedError) as exc_info:
        provider.fetch_transactions({}, "acc_1", "01/01/2026")
    assert "no tiene integración" in str(exc_info.value) or "no implementada" in str(exc_info.value)

    with pytest.raises(NotImplementedError):
        provider.get_auth_link("http://localhost:8000/cb", {})

    with pytest.raises(NotImplementedError):
        provider.confirm_auth("req_123", {})


def test_qonto_provider_fetch_transactions_raises_not_implemented():
    """QontoProvider no tiene implementada la descarga de transacciones y debe lanzar NotImplementedError."""
    provider = QontoProvider()
    with pytest.raises(NotImplementedError) as exc_info:
        provider.fetch_transactions({}, "qonto_main", "01/01/2026")
    assert "no implementada" in str(exc_info.value) or "Qonto" in str(exc_info.value)


def test_tink_provider_without_credentials_raises_value_error():
    """TinkProvider no debe inventar transacciones si no se configuran credenciales válidas."""
    provider = TinkProvider()
    with pytest.raises(ValueError) as exc_info:
        provider.fetch_transactions({}, "acc_1", "01/01/2026")
    assert "Credenciales de Tink no configuradas" in str(exc_info.value) or "Tink" in str(exc_info.value)
