import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.closing_service import ClosingService

@patch("app.domain.services.closing_service._get_connection")
def test_cierre_fiscal_calculo_impuestos_unit(mock_get_connection):
    """
    Test unitario para validar el cálculo de impuestos a liquidar en un periodo.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # 1. Simular año no cerrado
    mock_cursor.fetchone.return_value = None 
    
    # 2. Simular saldos de gastos e ingresos
    # [(account_code, total_debe, total_haber)]
    mock_cursor.fetchall.return_value = [
        {"account_code": "70000000", "total_debe": 0, "total_haber": 1000},
        {"account_code": "60000000", "total_debe": 500, "total_haber": 0}
    ]
    
    with patch("app.domain.services.closing_service.LedgerService") as MockLedgerService:
        res = ClosingService.close_fiscal_year(2026)
        
        assert res["status"] == "ok"
        assert res["resultado"] == 500.0
        assert "cerrado exitosamente" in res["message"]

@patch("app.domain.services.closing_service._get_connection")
def test_cierre_fiscal_generacion_asiento_regularizacion_unit(mock_get_connection):
    """
    Test unitario para validar la generación del asiento contable de regularización.
    """
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    mock_cursor.fetchone.return_value = None 
    mock_cursor.fetchall.return_value = [
        {"account_code": "70000000", "total_debe": 0, "total_haber": 1000},
        {"account_code": "60000000", "total_debe": 500, "total_haber": 0}
    ]
    
    with patch("app.domain.services.closing_service.LedgerService") as MockLedgerService:
        ClosingService.close_fiscal_year(2026)
        
        # Verificar que se llamó a LedgerService.record_journal_entry con el asiento correcto
        MockLedgerService.record_journal_entry.assert_called_once()
        args, kwargs = MockLedgerService.record_journal_entry.call_args
        ledger_entry = args[0]
        
        assert ledger_entry["concept"] == "Asiento de regularización cierre 2026"
        entries = ledger_entry["entries"]
        assert len(entries) == 3
        
        # Comprobar la regularización
        assert any(e["account"] == "12900000" and e["haber"] == 500.0 for e in entries)
