import pytest
from unittest.mock import patch
from app.tools.server.aeat_automation_tools import get_aeat_aggregated_data, generate_modelo_390_summary, generate_modelo_200_summary

@pytest.mark.asyncio
@patch('app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates')
async def test_get_aeat_aggregated_data_includes_disclaimer(mock_get):
    # Mock the underlying parser service to return dummy data
    mock_get.return_value = [
        {
            "year": 2026,
            "quarter": 1,
            "income": {"base": 1000.0, "iva": 210.0, "irpf": 150.0, "total": 1060.0, "count": 1},
            "expense": {"base": 500.0, "iva": 105.0, "irpf": 0.0, "total": 605.0, "count": 1},
            "net_result": 500.0
        }
    ]
    
    result = await get_aeat_aggregated_data(2026, 1)
    
    assert "legal_disclaimer" in result
    assert "AVISO LEGAL" in result["legal_disclaimer"]
    assert "estimación provisional" in result["legal_disclaimer"]

@pytest.mark.asyncio
@patch('app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates')
async def test_get_aeat_aggregated_data_empty_includes_disclaimer(mock_get):
    mock_get.return_value = []
    
    result = await get_aeat_aggregated_data(2026, 1)
    
    assert "legal_disclaimer" in result
    assert "AVISO LEGAL" in result["legal_disclaimer"]

@pytest.mark.asyncio
@patch('app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates')
async def test_generate_modelo_390_summary_includes_disclaimer(mock_get):
    mock_get.return_value = []
    
    result = await generate_modelo_390_summary(2026)
    
    assert "legal_disclaimer" in result
    assert "AVISO LEGAL" in result["legal_disclaimer"]

@pytest.mark.asyncio
@patch('app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates')
async def test_generate_modelo_200_summary_includes_disclaimer(mock_get):
    mock_get.return_value = []
    
    result = await generate_modelo_200_summary(2026)
    
    assert "legal_disclaimer" in result
    assert "AVISO LEGAL" in result["legal_disclaimer"]
