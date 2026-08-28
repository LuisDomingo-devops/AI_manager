import pytest
from datetime import datetime, timedelta
from app.tools.server.treasury_tools import get_cash_flow_forecast
from app.domain.services.tax_parser_service import TaxParserService
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor

@pytest.mark.asyncio
async def test_cash_flow_forecasting_logic():
    # 1. Limpiar e inicializar base de datos de pruebas
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM bank_movements")
        cursor.execute("DELETE FROM invoices")
        
        # Insertar movimientos bancarios
        # Saldo inicial = 5000.0 €
        cursor.execute("INSERT INTO bank_movements (movement_date, concept, amount) VALUES ('2026-08-01', 'Saldo inicial', 5000.0)")
        
        # Registrar gastos recurrentes (Autónomos los meses anteriores)
        cursor.execute("INSERT INTO bank_movements (movement_date, concept, amount) VALUES ('2026-06-30', 'Seguridad Social Autónomos Junio', -300.0)")
        cursor.execute("INSERT INTO bank_movements (movement_date, concept, amount) VALUES ('2026-07-31', 'Seguridad Social Autónomos Julio', -300.0)")
        
        conn.commit()
    finally:
        conn.close()

    # 2. Agregar factura de venta emitida y pendiente (Inflow previsto)
    # IVA 21%, Base 1000. Total = 1210 €. Fecha de emisión hoy.
    today_str = datetime.now().strftime("%Y-%m-%d")
    invoice_data = {
        "invoice_id": "INV-FLOW-101",
        "date": today_str,
        "issuer_name": "Luis Domingo Pérez",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente Flujo S.L.",
        "receiver_nif": "B11111111",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 1210.0,
        "category": "income",
        "quarter": 3,
        "year": 2026
    }
    # Guardar en base de datos cifrado
    TaxParserService.save_invoice_to_db(invoice_data)

    # 3. Ejecutar previsión de cash-flow
    # Saldo inicial = 5000 €
    # Gasto Autónomo mensual recurrente detectado = 300 € (proyectado a futuro en el horizonte)
    # Cobro previsto de factura = 1210 € (en 30 días)
    res = await get_cash_flow_forecast(horizon_days=90, safe_threshold=4000.0)
    assert res["status"] == "ok"
    assert res["current_balance"] == 4400.0
    
    # 7 días: sólo se descuenta el Autónomo si cae en el rango
    # 30 días: se descuenta Autónomos y se cobra la factura
    assert res["forecast_30d"] > 0
    assert len(res["events_projected"]) > 0

    # Comprobar que detectó el gasto recurrente de Autónomos
    has_ss_expense = any("Autónomos" in ev["description"] for ev in res["events_projected"])
    assert has_ss_expense is True

    # Comprobar si se generó alguna alerta de caída bajo el umbral seguro
    # Si bajamos de 4000.0 € (por ejemplo, después de aplicar Autónomos)
    # insertamos un movimiento de retiro grande para forzar alerta
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bank_movements (movement_date, concept, amount) VALUES ('2026-08-10', 'Compra Material', -4500.0)")
        conn.commit()
    finally:
        conn.close()

    res_alert = await get_cash_flow_forecast(horizon_days=30, safe_threshold=2000.0)
    assert len(res_alert["alerts"]) > 0
    assert res_alert["alerts"][0]["type"] == "threshold_breach"
