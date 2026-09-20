import pytest
import os
from app.infrastructure.adapters.bank_providers import BankProviderFactory

def test_provider_factory_production_mock():
    # Simulate production
    os.environ["ENV"] = "production"
    with pytest.raises(NotImplementedError):
        BankProviderFactory.get_provider("mock")
        
    os.environ["ENV"] = "development" # Reset
