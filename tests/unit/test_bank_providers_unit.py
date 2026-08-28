"""
Test Unitarios para los Proveedores Bancarios y de Pasarelas Financieras (Wise, Revolut, Qonto, Stripe, GoCardless, Mock).
"""
import pytest
from app.infrastructure.adapters.bank_providers import (
    BankProviderFactory,
    WiseProvider,
    RevolutProvider,
    QontoProvider,
    StripeProvider,
    GenericApiProvider,
    GoCardlessProvider,
    TinkProvider,
    PlaidProvider,
    MockBankProvider,
    BaseBankProvider
)

def test_bank_provider_factory_resolution():
    assert isinstance(BankProviderFactory.get_provider("wise"), WiseProvider)
    assert isinstance(BankProviderFactory.get_provider("WISE"), WiseProvider)
    assert isinstance(BankProviderFactory.get_provider("revolut"), RevolutProvider)
    assert isinstance(BankProviderFactory.get_provider("qonto"), QontoProvider)
    assert isinstance(BankProviderFactory.get_provider("stripe"), StripeProvider)
    assert isinstance(BankProviderFactory.get_provider("generic"), GenericApiProvider)
    assert isinstance(BankProviderFactory.get_provider("gocardless"), GoCardlessProvider)
    assert isinstance(BankProviderFactory.get_provider("psd2"), GoCardlessProvider)
    assert isinstance(BankProviderFactory.get_provider("tink"), TinkProvider)
    assert isinstance(BankProviderFactory.get_provider("plaid"), PlaidProvider)
    assert isinstance(BankProviderFactory.get_provider("mock"), MockBankProvider)
    assert isinstance(BankProviderFactory.get_provider("santander"), GoCardlessProvider)
    assert isinstance(BankProviderFactory.get_provider("abanca"), TinkProvider)

    with pytest.raises(ValueError) as exc:
        BankProviderFactory.get_provider("unknown_bank_xyz")
    assert "Proveedor contable desconocido" in str(exc.value)


def test_bank_provider_factory_supported_list():
    providers = BankProviderFactory.list_supported_direct_providers()
    assert len(providers) >= 4
    ids = [p["id"] for p in providers]
    assert "wise" in ids
    assert "revolut" in ids
    assert "qonto" in ids
    assert "stripe" in ids


def test_wise_provider_auth_link_and_validation():
    provider = WiseProvider()
    
    # Enlace oficial
    link_live = provider.get_auth_link("http://localhost:8000/callback", {})
    assert "wise.com/settings/api-tokens" in link_live
    
    link_sandbox = provider.get_auth_link("http://localhost:8000/callback", {"sandbox": True})
    assert "sandbox.transferwise.tech" in link_sandbox

    # Validación con token vacío
    val_empty = provider.validate_credentials({"api_token": ""})
    assert val_empty["valid"] is False
    assert "no puede estar vacío" in val_empty["error"]

    # Validación con token mock
    val_mock = provider.validate_credentials({"api_token": "mock_wise_token_123"})
    assert val_mock["valid"] is True
    assert "profile_id" in val_mock


def test_wise_provider_fetch_transactions_mock():
    provider = WiseProvider()
    txs = provider.fetch_transactions({"api_token": "mock_token"}, "acc_wise_1", "01/08/2026")
    assert len(txs) == 2
    assert any("Wise Transfer" in t["concept"] for t in txs)
    assert any(t["amount"] > 0 for t in txs)
    assert any(t["amount"] < 0 for t in txs)


def test_revolut_provider_unit():
    provider = RevolutProvider()
    assert "business.revolut.com" in provider.get_auth_link("http://localhost/cb", {})
    
    val_empty = provider.validate_credentials({"api_token": ""})
    assert val_empty["valid"] is False
    
    val_mock = provider.validate_credentials({"api_token": "mock_rev_key"})
    assert val_mock["valid"] is True

    txs = provider.fetch_transactions({"api_token": "mock_rev_key"}, "acc_1", "01/08/2026")
    assert len(txs) >= 1
    assert any("Revolut" in t["concept"] for t in txs)


def test_qonto_provider_unit():
    provider = QontoProvider()
    assert "qonto.com" in provider.get_auth_link("http://localhost/cb", {})
    
    val_empty = provider.validate_credentials({})
    assert val_empty["valid"] is False

    val_mock = provider.validate_credentials({"secret_key": "mock_sec", "organization_slug": "my_org"})
    assert val_mock["valid"] is True

    txs = provider.fetch_transactions({"secret_key": "mock_sec"}, "qonto_1", "01/08/2026")
    assert len(txs) >= 1


def test_stripe_provider_unit():
    provider = StripeProvider()
    assert "dashboard.stripe.com" in provider.get_auth_link("http://localhost/cb", {})
    
    val_empty = provider.validate_credentials({"api_key": ""})
    assert val_empty["valid"] is False
    
    val_mock = provider.validate_credentials({"api_key": "mock_sk_test_123"})
    assert val_mock["valid"] is True

    txs = provider.fetch_transactions({"api_key": "mock_sk_test_123"}, "balance_1", "01/08/2026")
    assert len(txs) >= 1
    assert any("Stripe" in t["concept"] for t in txs)


def test_mock_bank_provider_unit():
    provider = MockBankProvider()
    link = provider.get_auth_link("http://localhost:8000/callback", {"bank_name": "Santander"})
    assert "/bank/mock-auth" in link
    
    confirm = provider.confirm_auth("req_123", {})
    assert confirm["status"] == "success"
    assert "mock_account_123" in confirm["accounts"]

    txs = provider.fetch_transactions({}, "mock_account_123", "01/08/2026")
    assert len(txs) == 2


def test_tink_provider_unit():
    provider = TinkProvider()
    val_empty = provider.validate_credentials({})
    assert val_empty["valid"] is False
    
    val_mock = provider.validate_credentials({"client_id": "mock_tink_id", "client_secret": "mock_sec"})
    assert val_mock["valid"] is True
    
    link = provider.get_auth_link("http://localhost:8000/callback", {"client_id": "real_client_id_123"})
    assert "link.tink.com" in link
    assert "market=ES" in link

    txs = provider.fetch_transactions({"client_id": "mock_id"}, "acc_1", "01/08/2026")
    assert len(txs) == 2
    assert any("Tink" in t["concept"] for t in txs)


def test_plaid_provider_unit():
    provider = PlaidProvider()
    val_empty = provider.validate_credentials({})
    assert val_empty["valid"] is False
    
    val_mock = provider.validate_credentials({"client_id": "mock_plaid_id", "secret": "mock_secret"})
    assert val_mock["valid"] is True
    
    txs = provider.fetch_transactions({}, "acc_1", "01/08/2026")
    assert len(txs) == 1
    assert any("Plaid" in t["concept"] for t in txs)
