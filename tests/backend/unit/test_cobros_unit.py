import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.collection_service import CollectionService

@patch('app.domain.services.collection_service.InvoiceRepository')
@patch('app.domain.services.collection_service._get_connection')
def test_cobros_registro_unit(mock_get_connection, mock_repo):
    """
    Test unitario para registrar un cobro y validar reglas de negocio (pagos parciales).
    """
    # Configurar mock de factura
    mock_repo.find_invoice_by_id.return_value = {
        "id": "mock_id",
        "total_amount": 100.0
    }
    
    # Configurar mock de BD
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mockear pagos anteriores (ej: 0 pagado)
    mock_cursor.fetchone.side_effect = [
        {"is_closed": False}, # fiscal_year
        {"paid": 20.0} # payments
    ]
    
    res = CollectionService.register_payment("mock_id", 30.0, "efectivo", "2026-09-07", "Test")
    
    assert res["status"] == "ok"
    assert res["outstanding_balance"] == 50.0
    # Verificamos que se insertó el pago pero NO se actualizó el estado a cobrada
    assert mock_cursor.execute.call_count >= 3 # check year, check paid, insert payment

@patch('app.domain.services.collection_service.InvoiceRepository')
@patch('app.domain.services.collection_service._get_connection')
def test_cobros_estado_factura_unit(mock_get_connection, mock_repo):
    """
    Test unitario para comprobar el cambio de estado de la factura tras el cobro total.
    """
    # Configurar mock de factura
    mock_repo.find_invoice_by_id.return_value = {
        "id": "mock_id",
        "total_amount": 100.0
    }
    
    # Configurar mock de BD
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_connection.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor
    
    # Mockear pagos anteriores
    mock_cursor.fetchone.side_effect = [
        {"is_closed": False}, # fiscal_year
        {"paid": 0.0} # payments
    ]
    
    res = CollectionService.register_payment("mock_id", 100.0, "transferencia", "2026-09-07", "Pago Total")
    
    assert res["status"] == "ok"
    assert res["outstanding_balance"] == 0.0
    
    # Verificar que se lanzó el UPDATE del status
    update_called = False
    for call in mock_cursor.execute.call_args_list:
        if "UPDATE invoices SET status = 'cobrada'" in call[0][0]:
            update_called = True
    assert update_called, "No se actualizó el estado a 'cobrada'"

