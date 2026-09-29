"""
QA Test Suite para Certificación del Pipeline de Extracción de Facturas (Spec 015).
Certifica formalmente:
- SC-001: Soporte exhaustivo para formatos decimales (. y ,) y no alucinación de tasas.
- SC-002: CERO excepciones Pydantic ValidationError propagadas hacia capas superiores.
- SC-003: Resolución exacta del caso de regresión ("total = 41,76 €, base = 34,51 €, IVA = 21%").
- Robustez ante datos OCR ruidosos, símbolos monetarios internacionales y valores extremos.
"""

import pytest
import json
import random
from unittest.mock import patch

from app.domain.services.tax_parser_service import TaxParserService


@pytest.mark.asyncio
async def test_qa_sc003_exact_regression_verification():
    """
    SC-003: Verifica que el caso específico documentado en el Contrato de Discovery
    'total = 41,76 €, base imponible = 34,51 €, IVA = 21%'
    genere exactamente:
    base_imponible = 34.51
    iva_amount = 7.25
    iva_rate = 21.0
    total_amount = 41.76
    """
    raw_invoice_text = "total = 41,76 €, base imponible = 34,51 €, IVA = 21%"

    mock_llm_response = json.dumps({
        "invoice_id": "DISCOVERY-P06",
        "date": "2026-09-27",
        "issuer_name": "Proveedor Discovery",
        "issuer_nif": "B12345678",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "34,51",
        "iva_rate": "21%",
        "iva_amount": "7,25",
        "irpf_amount": "0,00",
        "total_amount": "41,76"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        result = TaxParserService.parse_invoice_text(raw_invoice_text)

        assert result["base_imponible"] == 34.51, "Base imponible debe ser exactamente 34.51"
        assert result["iva_amount"] == 7.25, "IVA amount debe ser exactamente 7.25"
        assert result["iva_rate"] == 21.0, "IVA rate debe ser exactamente 21.0 (ajustado al tramo legal)"
        assert result["total_amount"] == 41.76, "Total amount debe ser exactamente 41.76"


@pytest.mark.asyncio
async def test_qa_sc002_zero_pydantic_validation_error_leakage_on_out_of_bounds():
    """
    SC-002: Inyecta múltiples combinaciones de tasas fuera de rango (>100, negativas, alucinaciones)
    y verifica que NINGUNA lance una excepción Pydantic ValidationError no capturada.
    """
    hallucinated_rates = [
        503.47, 1000.0, 9999.99, -21.0, -0.01, 100.01, 250.0, 50347.0
    ]

    for bad_rate in hallucinated_rates:
        mock_llm_response = json.dumps({
            "invoice_id": f"QA-OOB-{int(abs(bad_rate))}",
            "date": "2026-09-27",
            "issuer_name": "Empresa Alucinada",
            "issuer_nif": "B12345678",
            "receiver_name": "Luis Domingo",
            "receiver_nif": "47019805P",
            "base_imponible": 1000.0,
            "iva_rate": bad_rate,
            "iva_amount": 210.0,
            "irpf_amount": 0.0,
            "total_amount": 1210.0
        })

        with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
            async def async_gen(*args, **kwargs):
                return mock_llm_response
            mock_generate.side_effect = async_gen

            # No debe lanzar ValidationError
            result = TaxParserService.parse_invoice_text(f"Factura con tasa alucinada {bad_rate}")

            # iva_rate retornado NUNCA debe ser mayor a 100
            assert 0.0 <= result["iva_rate"] <= 100.0, f"iva_rate {result['iva_rate']} superó los límites permitidos"


@pytest.mark.asyncio
async def test_qa_noisy_ocr_text_and_symbol_cleaning():
    """
    Verifica que textos ruidosos con múltiples monedas y espacios
    se desinfecten correctamente sin provocar fallos de casteo numérico.
    """
    noisy_inputs = [
        {"base": " 1200.50 € ", "rate": " 21 % ", "iva": " 252.11 EUR ", "tot": " 1452.61 € "},
        {"base": "$500,00", "rate": "10%", "iva": "$50,00", "tot": "$550,00"},
        {"base": "1.000,00 EUR", "rate": "4.0 %", "iva": "40,00 EUR", "tot": "1.040,00 EUR"}
    ]

    for idx, sample in enumerate(noisy_inputs):
        mock_llm_response = json.dumps({
            "invoice_id": f"QA-NOISE-{idx}",
            "date": "2026-09-27",
            "issuer_name": "Noisy OCR Vendor",
            "issuer_nif": "B99887766",
            "receiver_name": "Luis Domingo",
            "receiver_nif": "47019805P",
            "base_imponible": sample["base"],
            "iva_rate": sample["rate"],
            "iva_amount": sample["iva"],
            "irpf_amount": 0.0,
            "total_amount": sample["tot"]
        })

        with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
            async def async_gen(*args, **kwargs):
                return mock_llm_response
            mock_generate.side_effect = async_gen

            result = TaxParserService.parse_invoice_text("Texto con OCR sucio")
            assert isinstance(result["base_imponible"], float)
            assert isinstance(result["iva_rate"], float)
            assert isinstance(result["iva_amount"], float)
            assert isinstance(result["total_amount"], float)
            assert result["iva_rate"] <= 100.0


@pytest.mark.asyncio
async def test_qa_extreme_monetary_values_safety():
    """
    Verifica que facturas de importes muy elevados (ej: cientos de miles de euros)
    no causen desbordamiento ni confusión entre importes y tasas.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "QA-EXTREME-01",
        "date": "2026-09-27",
        "issuer_name": "Gran Maquinaria Industrial",
        "issuer_nif": "A12345678",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 500000.00,
        "iva_rate": 21.0,
        "iva_amount": 105000.00,
        "irpf_amount": 0.0,
        "total_amount": 605000.00
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        result = TaxParserService.parse_invoice_text("Factura maquinaria 500k")
        assert result["base_imponible"] == 500000.00
        assert result["iva_amount"] == 105000.00
        assert result["iva_rate"] == 21.0
        assert result["total_amount"] == 605000.00


@pytest.mark.asyncio
async def test_qa_manual_confirmation_flag_on_unresolvable_validation_error():
    """
    Verifica que cuando un documento presenta datos completamente incoherentes
    (ej: base_imponible = 0 o total negativo), se establezca requires_manual_confirmation = True
    y status = 'PENDIENTE_REVISION' sin lanzar excepciones.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "QA-BROKEN-01",
        "date": "2026-09-27",
        "issuer_name": "Broken Data",
        "issuer_nif": "INVALID_NIF",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 0.0,
        "iva_rate": 21.0,
        "iva_amount": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 0.0
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        result = TaxParserService.parse_invoice_text("Factura con datos corruptos")
        assert result["requires_manual_confirmation"] is True
        assert result["status"] == "PENDIENTE_REVISION"
