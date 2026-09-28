"""
Test de integración de resiliencia en adaptadores bancarios (Wise, Revolut, Stripe).
Verifica que las peticiones y parseos manejen excepciones tipadas de HTTP y formato
sin capturas genéricas ni imports tardíos de error_logger.
"""

import inspect
import pytest
from unittest.mock import patch, MagicMock
import httpx
from app.infrastructure.adapters import bank_providers
from app.infrastructure.adapters.bank_providers import (
    WiseProvider, RevolutProvider, StripeProvider
)

def test_bank_providers_no_inline_error_logger_imports():
    """Verifica que bank_providers.py no contenga imports tardíos de error_logger."""
    source = inspect.getsource(bank_providers)
    assert '    from app.utils.logger import error_logger' not in source, (
        "bank_providers.py aún contiene imports inline tardíos de error_logger"
    )

def test_wise_provider_balance_discovery_http_error_resilience():
    """Verifica que WiseProvider tolere fallos HTTP al descubrir balances sin romper la validación."""
    provider = WiseProvider()
    with patch("httpx.get") as mock_get:
        # Mock primer get de perfiles exitoso
        resp_profiles = MagicMock()
        resp_profiles.status_code = 200
        resp_profiles.json.return_value = [{"id": 12345, "type": "personal"}]
        
        # Mock segundo get de balances falla por timeout o error de conexión HTTP
        def side_effect(url, **kwargs):
            if "balances" in url:
                raise httpx.ConnectTimeout("Error de conexión con Wise")
            return resp_profiles

        mock_get.side_effect = side_effect

        result = provider.validate_credentials({"api_token": "valid_token_test", "profile_id": "12345"})
        assert result["valid"] is True
        assert result["accounts"] == []

def test_wise_provider_fetch_transactions_amount_parse_error():
    """Verifica que WiseProvider gestione montos no convertibles sin interrumpir la extracción."""
    provider = WiseProvider()
    with patch("httpx.get") as mock_get:
        resp_stmt = MagicMock()
        resp_stmt.status_code = 404

        resp_act = MagicMock()
        resp_act.status_code = 200
        resp_act.json.return_value = {
            "activities": [
                {
                    "createdOn": "2026-03-01T10:00:00Z",
                    "title": "Pago recibido",
                    "primaryAmount": "NO_NUMERIC_AMOUNT EUR",
                    "id": "act_101"
                }
            ]
        }
        mock_get.side_effect = lambda url, **kwargs: resp_act if "activities" in url else resp_stmt

        txs = provider.fetch_transactions({"api_token": "valid_token", "profile_id": "prof_101"}, "act_101", "2026-03-01")
        assert len(txs) == 1
        assert txs[0]["amount"] == 0.0

def test_revolut_provider_fetch_transactions_network_resilience():
    """Verifica que RevolutProvider tolere errores HTTP de red retornando lista vacía y registrando log."""
    provider = RevolutProvider()
    with patch("httpx.get", side_effect=httpx.NetworkError("Revolut API unreachable")):
        txs = provider.fetch_transactions({"api_token": "rev_live_key"}, "acc_1", "2026-03-01")
        assert txs == []

def test_stripe_provider_fetch_transactions_network_resilience():
    """Verifica que StripeProvider tolere errores HTTP retornando lista vacía."""
    provider = StripeProvider()
    with patch("httpx.get", side_effect=httpx.HTTPStatusError("Bad Gateway", request=MagicMock(), response=MagicMock(status_code=502))):
        txs = provider.fetch_transactions({"api_key": "sk_live_stripe"}, "acc_1", "2026-03-01")
        assert txs == []
