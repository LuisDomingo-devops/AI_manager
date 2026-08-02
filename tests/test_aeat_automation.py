import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.server.aeat_automation_tools import (
    get_aeat_aggregated_data,
    generate_modelo_303_autofill_script,
    fill_modelo_303_playwright
)

@pytest.mark.asyncio
async def test_get_aeat_aggregated_data_empty():
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=[]):
        res = await get_aeat_aggregated_data(2026, 1)
        assert res["quarter"] == 1
        assert res["income"]["base"] == 0.0
        assert res["expense"]["base"] == 0.0

@pytest.mark.asyncio
async def test_get_aeat_aggregated_data_with_values():
    mock_data = [{
        "year": 2026,
        "quarter": 1,
        "income": {"base": 1000.0, "iva": 210.0, "irpf": 0.0, "total": 1210.0, "count": 1},
        "expense": {"base": 100.0, "iva": 21.0, "irpf": 0.0, "total": 121.0, "count": 1},
        "net_result": 900.0
    }]
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=mock_data):
        res = await get_aeat_aggregated_data(2026, 1)
        assert res["quarter"] == 1
        assert res["income"]["base"] == 1000.0
        assert res["expense"]["base"] == 100.0

@pytest.mark.asyncio
async def test_generate_modelo_303_autofill_script():
    mock_data = [{
        "year": 2026,
        "quarter": 1,
        "income": {"base": 1500.0, "iva": 315.0, "irpf": 0.0, "total": 1815.0, "count": 1},
        "expense": {"base": 200.0, "iva": 42.0, "irpf": 0.0, "total": 242.0, "count": 1},
        "net_result": 1300.0
    }]
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=mock_data):
        res = await generate_modelo_303_autofill_script(2026, 1)
        assert res["status"] == "ok"
        assert "1500.0" in res["script"]
        assert "315.0" in res["script"]
        assert "200.0" in res["script"]
        assert "42.0" in res["script"]
        assert res["data_used"]["income_base"] == 1500.0
        assert res["data_used"]["expense_base"] == 200.0
