import re
path1 = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\tests\backend\integration\test_tax_multiterritory.py'
with open(path1, 'r', encoding='utf-8') as f:
    c1 = f.read()

c1 = c1.replace('''            '{"iva_rate": 4.0, "confidence": 0.95}',  # navarra_ok''', '''            '{"confidence": 0.50}',                   # can_inf\n            '{"iva_rate": 4.0, "confidence": 0.95}',  # navarra_ok''')

with open(path1, 'w', encoding='utf-8') as f:
    f.write(c1)

path2 = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\tests\backend\qa\test_phase5_audit_remediation_suite.py'
with open(path2, 'r', encoding='utf-8') as f:
    c2 = f.read()

c2 = c2.replace('''    rates_info = TaxEngine.resolve_rates_with_confidence(text_without_vat)
    assert rates_info["is_iva_inferred"] is True
    assert rates_info["requires_manual_confirmation"] is True
    assert rates_info["confidence_score"] <= 0.70

    # 2. Texto con IVA explícito
    text_with_vat = "Factura de servicios profesionales Base 1000 EUR, IVA 21%, Total 1210 EUR."
    rates_info_explicit = TaxEngine.resolve_rates_with_confidence(text_with_vat)
    assert rates_info_explicit["is_iva_inferred"] is False
    assert rates_info_explicit["requires_manual_confirmation"] is False
    assert rates_info_explicit["iva_rate"] == 21.0
    assert rates_info_explicit["confidence_score"] == 1.0

    # 3. Texto con exención legal (Art. 20)
    text_exempt = "Honorarios médicos. Operación exenta de IVA según Art. 20 Ley 37/1992. Total 150 EUR."
    rates_info_exempt = TaxEngine.resolve_rates_with_confidence(text_exempt)
    assert rates_info_exempt["iva_rate"] == 0.0
    assert rates_info_exempt["is_iva_inferred"] is False''', '''    from unittest.mock import patch, AsyncMock
    with patch("app.domain.services.tax_engine.GeminiClient.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = ['{"confidence": 0.5}', '{"iva_rate": 21.0, "confidence": 1.0}', '{"iva_rate": 0.0, "confidence": 1.0}']
        
        rates_info = TaxEngine.resolve_rates_with_confidence(text_without_vat)
        assert rates_info["is_iva_inferred"] is True
        assert rates_info["requires_manual_confirmation"] is True
        assert rates_info["confidence_score"] <= 0.70

        # 2. Texto con IVA explícito
        text_with_vat = "Factura de servicios profesionales Base 1000 EUR, IVA 21%, Total 1210 EUR."
        rates_info_explicit = TaxEngine.resolve_rates_with_confidence(text_with_vat)
        assert rates_info_explicit["is_iva_inferred"] is False
        assert rates_info_explicit["requires_manual_confirmation"] is False
        assert rates_info_explicit["iva_rate"] == 21.0
        assert rates_info_explicit["confidence_score"] == 1.0

        # 3. Texto con exención legal (Art. 20)
        text_exempt = "Honorarios médicos. Operación exenta de IVA según Art. 20 Ley 37/1992. Total 150 EUR."
        rates_info_exempt = TaxEngine.resolve_rates_with_confidence(text_exempt)
        assert rates_info_exempt["iva_rate"] == 0.0
        assert rates_info_exempt["is_iva_inferred"] is False''')

with open(path2, 'w', encoding='utf-8') as f:
    f.write(c2)
