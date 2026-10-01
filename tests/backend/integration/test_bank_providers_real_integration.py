"""
Test de Integración para Proveedores Bancarios Reales (User Story 5).
Valida el rechazo explícito y la erradicación total de fallbacks a datos simulados o ficticios.
"""

import pytest
from app.infrastructure.adapters.bank_providers import GoCardlessProvider


def test_bank_provider_rejects_missing_credentials_without_mocking():
    """Valida que ante credenciales ausentes o vacías no se generen datos falsos."""
    provider = GoCardlessProvider()
    
    # 1. Credenciales vacías deben fallar con error descriptivo o rechazo
    val_res = provider.validate_credentials({})
    assert val_res["valid"] is False
    assert "Secret ID" in val_res.get("error", "") or "credenciales" in val_res.get("error", "").lower()
    
    # 2. fetch_transactions debe lanzar excepción en vez de devolver transacciones simuladas
    with pytest.raises(ValueError) as excinfo:
        provider.fetch_transactions({}, account_id="acc-123", start_date="01/01/2026")
    assert "No se admiten simulaciones" in str(excinfo.value) or "configuradas" in str(excinfo.value)


def test_bank_provider_rejects_mock_credentials():
    """Valida que credenciales con prefijo 'mock_' no retornen datos falsos."""
    provider = GoCardlessProvider()
    
    mock_creds = {
        "secret_id": "mock_nordigen_id",
        "secret_key": "mock_nordigen_secret"
    }
    
    with pytest.raises(ValueError) as excinfo:
        provider.fetch_transactions(mock_creds, account_id="acc-fake", start_date="01/01/2026")
    assert "simulaciones" in str(excinfo.value).lower() or "credenciales" in str(excinfo.value).lower()
