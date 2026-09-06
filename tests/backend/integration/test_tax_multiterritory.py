import pytest
from unittest.mock import patch
from app.config import settings
from app.domain.services.tax_territory_factory import TaxTerritoryFactory
from app.domain.services.tax_engine import TaxEngine
from app.infrastructure.tax_territories.common_territory import CommonTerritoryAdapter
from app.infrastructure.tax_territories.canarias_territory import CanariasTerritoryAdapter
from app.infrastructure.tax_territories.navarra_territory import NavarraTerritoryAdapter
from app.infrastructure.tax_territories.pais_vasco_territory import PaisVascoTerritoryAdapter


def test_territory_adapters_integrity():
    # 1. Común
    common = CommonTerritoryAdapter()
    assert "comun" in common.calculate_tax_dues(100.0, 50.0)["territory"]
    assert 21.0 in common.get_supported_iva_rates()
    
    # 2. Canarias
    canarias = CanariasTerritoryAdapter()
    assert "canarias" in canarias.calculate_tax_dues(100.0, 50.0)["territory"]
    assert 7.0 in canarias.get_supported_iva_rates()
    assert 21.0 not in canarias.get_supported_iva_rates()

    # 3. Navarra
    navarra = NavarraTerritoryAdapter()
    assert "navarra" in navarra.calculate_tax_dues(100.0, 50.0)["territory"]
    
    # 4. País Vasco
    vasco = PaisVascoTerritoryAdapter()
    assert "pais_vasco" in vasco.calculate_tax_dues(100.0, 50.0)["territory"]


def test_tax_territory_factory_resolution():
    # Limpiar caché de la factoría para el test
    TaxTerritoryFactory._cached_adapters.clear()
    
    with patch.object(settings, "FISCAL_TERRITORY", "comun"):
        adapter = TaxTerritoryFactory.get_current_territory()
        assert isinstance(adapter, CommonTerritoryAdapter)

    TaxTerritoryFactory._cached_adapters.clear()
    with patch.object(settings, "FISCAL_TERRITORY", "canarias"):
        adapter = TaxTerritoryFactory.get_current_territory()
        assert isinstance(adapter, CanariasTerritoryAdapter)

    TaxTerritoryFactory._cached_adapters.clear()
    with patch.object(settings, "FISCAL_TERRITORY", "navarra"):
        adapter = TaxTerritoryFactory.get_current_territory()
        assert isinstance(adapter, NavarraTerritoryAdapter)

    TaxTerritoryFactory._cached_adapters.clear()
    with patch.object(settings, "FISCAL_TERRITORY", "pais_vasco"):
        adapter = TaxTerritoryFactory.get_current_territory()
        assert isinstance(adapter, PaisVascoTerritoryAdapter)


def test_tax_engine_ocr_resolution_multiterritory():
    # 1. Caso Régimen Común
    TaxTerritoryFactory._cached_adapters.clear()
    
    from unittest.mock import patch, AsyncMock
    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = [
            '{"iva_rate": 21.0, "confidence": 0.95}', # comun_ok
            '{"iva_rate": 7.0, "confidence": 0.95}',  # comun_err
            '{"iva_rate": 7.0, "confidence": 0.95}',  # can_ok
            '{"iva_rate": 21.0, "confidence": 0.95}', # can_err
            '{}',                                     # can_inf (sin IVA explícito)
            '{"iva_rate": 4.0, "confidence": 0.95}',  # navarra_ok
        ]
        with patch.object(settings, "FISCAL_TERRITORY", "comun"):
            # Texto con IVA del 21% (soportado en régimen común)
            res_comun_ok = TaxEngine.resolve_rates_with_confidence("Factura con base 100€ e IVA 21%")
            assert res_comun_ok["iva_rate"] == 21.0
            assert res_comun_ok["requires_manual_confirmation"] is False
            
            # Texto con IGIC del 7% (no soportado en régimen común)
            res_comun_err = TaxEngine.resolve_rates_with_confidence("Factura canaria con IGIC 7%")
            assert res_comun_err["iva_rate"] == 7.0
            assert res_comun_err["requires_manual_confirmation"] is True  # Requiere confirmación por no estar soportada
            assert res_comun_err["confidence_score"] == 0.50
    
        # 2. Caso Canarias (IGIC)
        TaxTerritoryFactory._cached_adapters.clear()
        with patch.object(settings, "FISCAL_TERRITORY", "canarias"):
            # Texto con IGIC del 7% (soportado en Canarias)
            res_can_ok = TaxEngine.resolve_rates_with_confidence("Factura con IGIC 7%")
            assert res_can_ok["iva_rate"] == 7.0
            assert res_can_ok["requires_manual_confirmation"] is False
    
            # Texto con IVA del 21% (no soportado en Canarias)
            res_can_err = TaxEngine.resolve_rates_with_confidence("Factura de la península con IVA 21%")
            assert res_can_err["iva_rate"] == 21.0
            assert res_can_err["requires_manual_confirmation"] is True  # Requiere confirmación por no estar soportada en Canarias
            assert res_can_err["confidence_score"] == 0.50
            
            # Inferencia de tasa por defecto en caso de ausencia
            res_can_inf = TaxEngine.resolve_rates_with_confidence("Factura sin tasas explícitas")
            assert res_can_inf["iva_rate"] == 0.0  # El motor de fallback devuelve 0.0 cuando no encuentra tasas explícitas
            assert res_can_inf["is_iva_inferred"] is True
            
        # 3. Caso Navarra (Hacienda Foral)
        TaxTerritoryFactory._cached_adapters.clear()
        with patch.object(settings, "FISCAL_TERRITORY", "navarra"):
            res_navarra_ok = TaxEngine.resolve_rates_with_confidence("Factura con IVA foral 4%")
            assert res_navarra_ok["iva_rate"] == 4.0
            assert res_navarra_ok["requires_manual_confirmation"] is False
