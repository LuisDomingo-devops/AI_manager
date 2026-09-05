import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.server.aeat_automation_tools import (
    get_aeat_aggregated_data,
    generate_modelo_303_autofill_script,
    fill_modelo_303_playwright,
    fill_modelo_303_guardian,
    fill_modelo_130_guardian,
    generate_modelo_390_summary,
    generate_modelo_190_summary,
    generate_modelo_180_summary
)
from app.utils.encryption import encryptor

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
        res = await generate_modelo_303_autofill_script(2026, 1, confirmed_by_user=True)
        assert res["status"] == "ok"
        assert "1500.0" in res["script"]
        assert "315.0" in res["script"]
        assert "200.0" in res["script"]
        assert "42.0" in res["script"]
        assert res["data_used"]["income_base"] == 1500.0
        assert res["data_used"]["expense_base"] == 200.0


@pytest.mark.asyncio
async def test_fill_modelo_303_guardian_no_confirmation():
    res = await fill_modelo_303_guardian(2026, 1, confirmed_by_user=False)
    assert res["status"] == "pending_confirmation"
    assert "confirmar" in res["message"].lower() or "continuar" in res["message"].lower()


@pytest.mark.asyncio
async def test_fill_modelo_303_guardian_no_connection():
    mock_data = [{
        "year": 2026,
        "quarter": 1,
        "income": {"base": 1500.0, "iva": 315.0, "irpf": 0.0, "total": 1815.0, "count": 1},
        "expense": {"base": 200.0, "iva": 42.0, "irpf": 0.0, "total": 242.0, "count": 1},
        "net_result": 1300.0
    }]
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=mock_data):
        with patch("app.core.websocket_manager.guardian_ws_manager.active_connections", []):
            res = await fill_modelo_303_guardian(2026, 1, confirmed_by_user=True)
            assert res["status"] == "error"
            assert "conexión" in res["message"].lower() or "conectada" in res["message"].lower()


@pytest.mark.asyncio
async def test_fill_modelo_303_guardian_success():
    mock_data = [{
        "year": 2026,
        "quarter": 1,
        "income": {"base": 1500.0, "iva": 315.0, "irpf": 0.0, "total": 1815.0, "count": 1},
        "expense": {"base": 200.0, "iva": 42.0, "irpf": 0.0, "total": 242.0, "count": 1},
        "net_result": 1300.0
    }]
    
    mock_connection = MagicMock()
    mock_send = AsyncMock()
    
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=mock_data):
        with patch("app.core.websocket_manager.guardian_ws_manager.active_connections", [mock_connection]):
            with patch("app.core.websocket_manager.guardian_ws_manager.send_json", mock_send) as mock_send_method:
                res = await fill_modelo_303_guardian(2026, 1, confirmed_by_user=True)
                assert res["status"] == "ok"
                assert res["data_used"]["income_base"] == 1500.0
                
                # Debería haber enviado dos mensajes: autocompletar y toast
                assert mock_send_method.call_count == 2
                
                # Verificar payload de autocompletar
                call_args_autofill = mock_send_method.call_args_list[0][0][0]
                assert call_args_autofill["action"] == "guardian.autofill"
                assert call_args_autofill["params"]["fields"]["input[id$='C01']"] == "1500.0"
                
                # Verificar payload de alert
                call_args_alert = mock_send_method.call_args_list[1][0][0]
                assert call_args_alert["action"] == "guardian.alert"
                assert call_args_alert["params"]["type"] == "success"


@pytest.mark.asyncio
async def test_fill_modelo_130_guardian_success():
    mock_data = [{
        "year": 2026,
        "quarter": 1,
        "income": {"base": 1000.0, "iva": 0.0, "irpf": 0.0, "total": 1000.0, "count": 1},
        "expense": {"base": 200.0, "iva": 0.0, "irpf": 0.0, "total": 200.0, "count": 1},
        "net_result": 800.0
    }]
    
    mock_connection = MagicMock()
    mock_send = AsyncMock()
    
    with patch("app.domain.services.tax_parser_service.TaxParserService.get_quarterly_aggregates", return_value=mock_data):
        with patch("app.core.websocket_manager.guardian_ws_manager.active_connections", [mock_connection]):
            with patch("app.core.websocket_manager.guardian_ws_manager.send_json", mock_send) as mock_send_method:
                res = await fill_modelo_130_guardian(2026, 1, confirmed_by_user=True)
                assert res["status"] == "ok"
                assert res["data_used"]["net_result"] == 800.0
                assert res["data_used"]["pago_fraccionado"] == 160.0  # 800 * 20%
                
                # Debería haber enviado dos mensajes: autocompletar y toast
                assert mock_send_method.call_count == 2
                
                call_args_autofill = mock_send_method.call_args_list[0][0][0]
                assert call_args_autofill["action"] == "guardian.autofill"
                assert call_args_autofill["params"]["fields"]["input[id$='C01']"] == "1000.0"
                assert call_args_autofill["params"]["fields"]["input[id$='C02']"] == "200.0"
                assert call_args_autofill["params"]["fields"]["input[id$='C04']"] == "160.0"


@pytest.mark.asyncio
async def test_generate_modelo_390_summary():
    mock_invoices = [
        # Ingresos
        {"category": "income", "base_imponible": encryptor.encrypt("2000.0"), "iva_amount": encryptor.encrypt("420.0"), "iva_rate": 21.0},
        {"category": "income", "base_imponible": encryptor.encrypt("500.0"), "iva_amount": encryptor.encrypt("50.0"), "iva_rate": 10.0},
        # Gastos
        {"category": "expense", "base_imponible": encryptor.encrypt("300.0"), "iva_amount": encryptor.encrypt("63.0"), "iva_rate": 21.0}
    ]
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = mock_invoices
    mock_conn.cursor.return_value.execute.return_value.fetchall.return_value = mock_invoices
    with patch("app.domain.services.annual_tax_service._get_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        res = await generate_modelo_390_summary(2026)
        assert res["status"] == "ok"
        sum_data = res["summary"]
        assert sum_data["devengado"]["21"]["base"] == 2000.0
        assert sum_data["devengado"]["21"]["cuota"] == 420.0
        assert sum_data["devengado"]["10"]["base"] == 500.0
        assert sum_data["devengado"]["10"]["cuota"] == 50.0
        assert sum_data["deducible"]["total_base"] == 300.0
        assert sum_data["deducible"]["total_cuota"] == 63.0
        assert sum_data["resultado"] == 407.0  # (420+50) - 63


@pytest.mark.asyncio
async def test_generate_modelo_190_summary():
    mock_payrolls = [
        {"employee_id": 1, "gross_total": 2500.0, "irpf_amount": 250.0}
    ]
    mock_employee = {
        "nif_encrypted": encryptor.encrypt("12345678X"),
        "full_name_encrypted": encryptor.encrypt("Empleado Uno")
    }
    mock_expenses = [
        # Gasto con retención de profesional
        {"issuer_nif": encryptor.encrypt("87654321Z"), "issuer_name": encryptor.encrypt("Colaborador Pro"), "base_imponible": encryptor.encrypt("1000.0"), "irpf_amount": encryptor.encrypt("150.0")}
    ]

    mock_conn = MagicMock()
    # Primera llamada obtiene payrolls, segunda expenses
    mock_conn.execute.return_value.fetchall.side_effect = [mock_payrolls, mock_expenses]
    mock_conn.execute.return_value.fetchone.return_value = mock_employee
    mock_conn.cursor.return_value.execute.return_value.fetchall.side_effect = [mock_payrolls, mock_expenses]
    mock_conn.cursor.return_value.execute.return_value.fetchone.return_value = mock_employee
    
    with patch("app.domain.services.annual_tax_service._get_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        res = await generate_modelo_190_summary(2026)
        assert res["status"] == "ok"
        sum_data = res["summary"]
        assert sum_data["total_perceptores"] == 2
        assert sum_data["total_percepciones"] == 3500.0  # 2500 + 1000
        assert sum_data["total_retenciones"] == 400.0    # 250 + 150
        
        perceptores = sum_data["perceptores"]
        claves = [p["clave"] for p in perceptores]
        assert "A" in claves
        assert "G" in claves


@pytest.mark.asyncio
async def test_generate_modelo_180_summary():
    mock_expenses = [
        # Gasto con retención y palabra de alquiler
        {"issuer_nif": encryptor.encrypt("99999999P"), "issuer_name": encryptor.encrypt("Arrendador Uno"), "base_imponible": encryptor.encrypt("1200.0"), "irpf_amount": encryptor.encrypt("228.0"), "concept": encryptor.encrypt("Alquiler mensual oficina principal")},
        # Gasto con retención pero que NO es de alquiler
        {"issuer_nif": encryptor.encrypt("88888888Q"), "issuer_name": encryptor.encrypt("Gestoria S.L."), "base_imponible": encryptor.encrypt("100.0"), "irpf_amount": encryptor.encrypt("15.0"), "concept": encryptor.encrypt("Asesoria fiscal trimestral")}
    ]
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = mock_expenses
    mock_conn.cursor.return_value.execute.return_value.fetchall.return_value = mock_expenses
    
    with patch("app.domain.services.annual_tax_service._get_connection") as mock_get_conn:
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        res = await generate_modelo_180_summary(2026)
        assert res["status"] == "ok"
        sum_data = res["summary"]
        assert sum_data["total_arrendadores"] == 1
        assert sum_data["total_bases"] == 1200.0
        assert sum_data["total_retenciones"] == 228.0
        assert sum_data["arrendadores"][0]["nif"] == "99999999P"
