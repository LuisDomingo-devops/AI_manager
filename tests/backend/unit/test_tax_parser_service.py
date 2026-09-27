import pytest
import json
from unittest.mock import patch, MagicMock

from app.domain.services.tax_parser_service import TaxParserService

@pytest.mark.asyncio
async def test_mixed_format_extraction_regression():
    """
    T001 [US1] Verifica que valores > 100 en iva_rate (ej 503.47)
    sean corregidos (intercambiados con iva_amount) si coinciden lógicamente,
    impidiendo un fallo de validación posterior.
    """
    mock_llm_response = json.dumps({
        "invoice_id": "123",
        "date": "2026-09-27",
        "issuer_name": "Test",
        "issuer_nif": "B12345678",
        "receiver_name": "Me",
        "receiver_nif": "47019805P",
        "base_imponible": 2397.47,
        "iva_rate": 503.47,     # The LLM hallucinated the amount into the rate
        "iva_amount": 21.0,     # and the rate into the amount
        "irpf_amount": 0.0,
        "total_amount": 2900.94
    })
    
    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        # Mocking the async generate method
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen
        
        # We need to mock the event bus to avoid async issues during tests
        with patch("app.core.events.event_bus.publish"):
            # Also mock database insertion if any, but parse_invoice_text does not insert.
            # wait, parse_invoice_text only returns a dictionary.
            result = TaxParserService.parse_invoice_text("Factura Falsa")
            
            # The service should have swapped iva_rate and iva_amount
            assert result["iva_rate"] == 21.0
            assert result["iva_amount"] == 503.47

@pytest.mark.asyncio
async def test_resilient_extraction_fallback():
    """
    T004 [US2] Verifica que si los datos son irrecuperablemente erróneos 
    (ej: fallan validaciones de Pydantic y no se pueden arreglar), 
    la función no arroje ValidationError crudo sino que retorne una factura 
    parcial con requires_manual_confirmation = True.
    """
    # Devolver valores negativos donde no se puede
    mock_llm_response = json.dumps({
        "invoice_id": "123",
        "date": "2026-09-27",
        "issuer_name": "Test",
        "issuer_nif": "B12345678",
        "receiver_name": "Me",
        "receiver_nif": "47019805P",
        "base_imponible": -100.0, # Inválido
        "iva_rate": -21.0,        # Inválido
        "iva_amount": -21.0,      # Inválido
        "irpf_amount": 0.0,
        "total_amount": -121.0
    })

    with patch("app.infrastructure.adapters.llm_client.GeminiClient.generate") as mock_generate:
        async def async_gen(*args, **kwargs):
            return mock_llm_response
        mock_generate.side_effect = async_gen
        
        # Si la lógica intenta instanciar InvoiceSchema y falla, 
        # debe atraparlo y setear requires_manual_confirmation = True
        result = TaxParserService.parse_invoice_text("Factura Negativa")
        
        assert result["requires_manual_confirmation"] is True
