import pytest
from unittest.mock import patch
from app.domain.services.closing_service import ClosingService

@patch("app.domain.services.closing_service.LedgerService")
def test_cierre_fiscal_calculo_impuestos_unit(MockLedgerService):
    """
    Test unitario para validar que ClosingService delega en LedgerService.
    """
    MockLedgerService.close_fiscal_year.return_value = {
        "status": "ok", 
        "regularizacion_asiento_id": "test_id", 
        "message": "cerrado exitosamente"
    }
    
    res = ClosingService.close_fiscal_year(2026)
    
    assert res["status"] == "ok"
    assert "cerrado exitosamente" in res["message"]
    MockLedgerService.close_fiscal_year.assert_called_once_with(2026)

@patch("app.domain.services.closing_service.LedgerService")
def test_cierre_fiscal_generacion_asiento_regularizacion_unit(MockLedgerService):
    """
    Test unitario para validar que se llama a LedgerService de forma correcta.
    """
    ClosingService.close_fiscal_year(2026)
    MockLedgerService.close_fiscal_year.assert_called_once_with(2026)

