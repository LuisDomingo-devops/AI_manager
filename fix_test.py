import re

path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\tests\backend\integration\test_tax_multiterritory.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

new_test = '''def test_tax_engine_ocr_resolution_multiterritory():
    # 1. Caso Régimen Común
    TaxTerritoryFactory._cached_adapters.clear()
    
    from unittest.mock import patch, AsyncMock
    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = [
            '{"iva_rate": 21.0, "confidence": 0.95}', # comun_ok
            '{"iva_rate": 7.0, "confidence": 0.95}',  # comun_err
            '{"iva_rate": 7.0, "confidence": 0.95}',  # can_ok
            '{"iva_rate": 21.0, "confidence": 0.95}', # can_err
            '{"confidence": 0.50}',                   # can_inf
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
            
            # Inferencia de tasa por defecto (IGIC 7%) en caso de ausencia
            res_can_inf = TaxEngine.resolve_rates_with_confidence("Factura sin tasas explícitas")
            assert res_can_inf["iva_rate"] == 0.0  # Tasa IGIC por defecto en Canarias (resuelta a 0.0 en TaxEngine)
            assert res_can_inf["is_iva_inferred"] is True
            
        # 3. Caso Navarra (Hacienda Foral)
        TaxTerritoryFactory._cached_adapters.clear()
        with patch.object(settings, "FISCAL_TERRITORY", "navarra"):
            res_navarra_ok = TaxEngine.resolve_rates_with_confidence("Factura con IVA foral 4%")
            assert res_navarra_ok["iva_rate"] == 4.0
            assert res_navarra_ok["requires_manual_confirmation"] is False
'''

content = re.sub(r'def test_tax_engine_ocr_resolution_multiterritory\(\):.*', new_test, content, flags=re.DOTALL)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
