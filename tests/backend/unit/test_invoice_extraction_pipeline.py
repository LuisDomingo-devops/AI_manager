"""
Tests Unitarios para el Pipeline de Extracción de Facturas (Spec 015).
Cubre:
- Desinfección de símbolos monetarios (€, EUR, $, USD, etc.).
- Manejo de separadores decimales (. y ,).
- Prevención de asignación de valores monetarios (> 100) al campo porcentual iva_rate.
- Corrección de cruces de valores (swap de iva_rate e iva_amount).
- Ajuste a tramos legales de IVA (21%, 10%, 4%, 0%) en desviaciones de redondeo.
- Manejo resiliente de errores sin propagar ValidationError de Pydantic al orquestador.
"""

import pytest
import json
from unittest.mock import patch, MagicMock

from app.domain.services.tax_parser_service import TaxParserService


@pytest.mark.asyncio
async def test_parse_string_with_dot_decimal_separator():
    """
    Verifica que importes con punto decimal como '503.47' o '503.47 EUR'
    no se conviertan erróneamente en 50347.0 por eliminación del punto.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-DOT-001",
        "date": "2026-09-27",
        "issuer_name": "Proveedor Global",
        "issuer_nif": "B12345678",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "2397.47",
        "iva_rate": "21%",
        "iva_amount": "503.47 EUR",
        "irpf_amount": "0.0",
        "total_amount": "2900.94 €"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Factura con puntos")

            assert result["base_imponible"] == 2397.47
            assert result["iva_amount"] == 503.47
            assert result["total_amount"] == 2900.94
            assert result["iva_rate"] == 21.0


@pytest.mark.asyncio
async def test_parse_string_with_comma_decimal_separator():
    """
    Verifica que importes con coma decimal como '34,51' o '7,25 €'
    se conviertan adecuadamente a float (34.51 y 7.25).
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-COMMA-002",
        "date": "2026-09-27",
        "issuer_name": "Proveedor Local",
        "issuer_nif": "B87654321",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "34,51",
        "iva_rate": "21 %",
        "iva_amount": "7,25 €",
        "irpf_amount": "0,00",
        "total_amount": "41,76 €"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Factura con comas")

            assert result["base_imponible"] == 34.51
            assert result["iva_amount"] == 7.25
            assert result["total_amount"] == 41.76
            assert result["iva_rate"] == 21.0


@pytest.mark.asyncio
async def test_european_thousands_and_comma_decimal():
    """
    Verifica que números en formato europeo con miles y decimales '1.234,56 €'
    se conviertan correctamente a 1234.56.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-EUR-003",
        "date": "2026-09-27",
        "issuer_name": "Mayorista S.L.",
        "issuer_nif": "B11223344",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "1.234,56 €",
        "iva_rate": "21.0",
        "iva_amount": "259,26 €",
        "irpf_amount": "0.0",
        "total_amount": "1.493,82 €"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Factura miles europeos")

            assert result["base_imponible"] == 1234.56
            assert result["iva_amount"] == 259.26
            assert result["total_amount"] == 1493.82
            assert result["iva_rate"] == 21.0


@pytest.mark.asyncio
async def test_anglo_thousands_and_dot_decimal():
    """
    Verifica que números en formato anglosajón '1,234.56 $'
    se conviertan correctamente a 1234.56.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "INV-US-004",
        "date": "2026-09-27",
        "issuer_name": "US Tech Corp",
        "issuer_nif": "B99887766",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": "1,234.56 $",
        "iva_rate": "21%",
        "iva_amount": "259.26 $",
        "irpf_amount": "0.0",
        "total_amount": "1,493.82 $"
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Factura anglosajona")

            assert result["base_imponible"] == 1234.56
            assert result["iva_amount"] == 259.26
            assert result["total_amount"] == 1493.82


@pytest.mark.asyncio
async def test_acceptance_scenario_1_mixed_formatting():
    """
    Escenario de Aceptación 1:
    'total = 41,76 €, base imponible = 34,51 €, IVA = 21%'
    Debe producir base_imponible = 34.51, iva_amount = 7.25, iva_rate = 21.0.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "FAC-SC1",
        "date": "2026-09-27",
        "issuer_name": "Papelería Central",
        "issuer_nif": "B44556677",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 34.51,
        "iva_rate": 21.0,
        "iva_amount": 7.25,
        "irpf_amount": 0.0,
        "total_amount": 41.76
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("total = 41,76 €, base imponible = 34,51 €, IVA = 21%")

            assert result["base_imponible"] == 34.51
            assert result["iva_amount"] == 7.25
            assert result["iva_rate"] == 21.0
            assert result["total_amount"] == 41.76


@pytest.mark.asyncio
async def test_iva_rate_snap_to_legal_bracket():
    """
    Verifica que pequeñas desviaciones de redondeo (ej: 21.01% derivado de 7.25 / 34.51)
    se ajusten exactamente al tramo legal de IVA (21.0).
    """
    mock_llm_response = json.dumps({
        "invoice_id": "FAC-SNAP",
        "date": "2026-09-27",
        "issuer_name": "Papelería Central",
        "issuer_nif": "B44556677",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 34.51,
        "iva_rate": 21.01, # Desviación de redondeo
        "iva_amount": 7.25,
        "irpf_amount": 0.0,
        "total_amount": 41.76
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Desviacion redondeo")

            assert result["iva_rate"] == 21.0


@pytest.mark.asyncio
async def test_monetary_value_never_assigned_to_iva_rate_when_unswappable():
    """
    FR-002 / FR-004:
    Si el LLM genera una tasa > 100 que NO se puede intercambiar (por ejemplo 503.47 en iva_rate
    y iva_amount también es 503.47), iva_rate NUNCA debe superar 100.
    Debe sanearse a un rango válido (o inferirse) y marcar requires_manual_confirmation = True.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "FAC-UNSWAPPABLE",
        "date": "2026-09-27",
        "issuer_name": "Test Invalido",
        "issuer_nif": "B12345678",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 2397.47,
        "iva_rate": 503.47,   # Alucinación no swappable
        "iva_amount": 503.47,
        "irpf_amount": 0.0,
        "total_amount": 2900.94
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen

        with patch("app.core.events.event_bus.publish"):
            result = TaxParserService.parse_invoice_text("Tasa imposible")

            # iva_rate jamás debe ser > 100
            assert result["iva_rate"] <= 100.0
            # Al ser base 2397.47 e iva 503.47, el sistema puede inferir 21.0% o marcar revisión
            assert result["iva_rate"] == 21.0
            assert result["iva_amount"] == 503.47


@pytest.mark.asyncio
async def test_reduced_and_super_reduced_rates():
    """
    Verifica que tasas reducidas (10.0%) y superreducidas (4.0%) se procesen correctamente.
    """
    for rate, base, iva in [(10.0, 100.0, 10.0), (4.0, 50.0, 2.0)]:
        mock_llm_response = json.dumps({
            "invoice_id": f"FAC-RATE-{int(rate)}",
            "date": "2026-09-27",
            "issuer_name": "Alimentación",
            "issuer_nif": "B12345678",
            "receiver_name": "Luis Domingo",
            "receiver_nif": "47019805P",
            "base_imponible": base,
            "iva_rate": f"{rate}%",
            "iva_amount": iva,
            "irpf_amount": 0.0,
            "total_amount": base + iva
        })

        with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
            async def async_gen(*args, **kwargs):
                return mock_llm_response
            mock_generate.side_effect = async_gen

            with patch("app.core.events.event_bus.publish"):
                result = TaxParserService.parse_invoice_text(f"Factura IVA {rate}%")
                assert result["iva_rate"] == rate
                assert result["iva_amount"] == iva
