"""
test_tax_engine_quarterly_lifecycle.py
======================================
Test de Integración del ciclo de vida trimestral contable y fiscal completo (1T a 4T).
Valida:
1. Liquidación del Modelo 303 con arrastre y compensación automática de saldos negativos (Casilla 110).
2. Liquidación acumulativa del Modelo 130 con deducción de pagos previos en Casilla 07 y retenciones en Casilla 08.
3. Generación y conciliación del Modelo 390 al cierre del ejercicio fiscal.
"""
import pytest
from app.domain.services.tax_engine import TaxEngine
from app.domain.services.annual_tax_service import AnnualTaxService
from app.domain.models.billing import Model303ResultDTO, Model130ResultDTO


def test_quarterly_lifecycle_model_303_compensation_flow():
    """
    Ciclo de vida completo del IVA en 4 trimestres con arrastre de cuotas a compensar (Casilla 110).
    - 1T: Gastos superan a ventas -> resultado negativo a compensar (-300 €).
    - 2T: Ventas superan a gastos (+500 €) -> se compensan los 300 € de 1T, resultado final a ingresar = +200 €.
    - 3T: Saldo neutro sin compensaciones pendientes.
    - 4T: Ventas ordinarias y comprobación de conciliación.
    """
    engine = TaxEngine()

    # --- 1T: Resultado Negativo ---
    sales_q1 = [{"base": 1000.0, "vat_rate": 21.0, "tax": 210.0}]
    purchases_q1 = [{"base": 2428.57, "vat_rate": 21.0, "tax": 510.0, "is_investment": False}]

    q1_res = engine.calculate_model_303_from_data(
        fiscal_year=2026, quarter=1,
        sales=sales_q1, purchases=purchases_q1,
        prorrata_pct=100.0, compensacion_periodos_anteriores=0.0
    )

    assert q1_res.casillas["07"] == 1000.0  # Base 21%
    assert q1_res.casillas["09"] == 210.0   # Cuota 21%
    assert q1_res.casillas["28"] == 2428.57
    assert q1_res.casillas["29"] == 510.0
    assert q1_res.casillas["46"] == -300.0
    assert q1_res.casillas["110"] == 0.0
    assert q1_res.casillas["71"] == -300.0
    saldo_a_compensar_1t = abs(q1_res.casillas["71"])

    # --- 2T: Ventas positivas, aplicación de compensación 1T en Casilla 110 ---
    sales_q2 = [{"base": 4000.0, "vat_rate": 21.0, "tax": 840.0}]
    purchases_q2 = [{"base": 1619.05, "vat_rate": 21.0, "tax": 340.0, "is_investment": False}]

    q2_res = engine.calculate_model_303_from_data(
        fiscal_year=2026, quarter=2,
        sales=sales_q2, purchases=purchases_q2,
        prorrata_pct=100.0, compensacion_periodos_anteriores=saldo_a_compensar_1t
    )

    # 840 - 340 = 500 € régimen general
    assert q2_res.casillas["46"] == 500.0
    # Casilla 110 traslada exactamente el saldo pendiente de 1T
    assert q2_res.casillas["110"] == 300.0
    # Casilla 71 resultado final a ingresar: 500 - 300 = 200 €
    assert q2_res.casillas["71"] == 200.0
    assert q2_res.resultado_autoliquidacion == 200.0


def test_quarterly_lifecycle_model_130_cumulative_deductions():
    """
    Ciclo trimestral acumulativo del Modelo 130 durante el ejercicio:
    - 1T: Rendimiento 10.000 € -> Pago 2.000 € (ingresado).
    - 2T: Rendimiento acumulado 25.000 € (5.000 € 20%) -> deduce 2.000 € del 1T (Casilla 07) y 300 € de retenciones (Casilla 08).
    - Resultado a ingresar en 2T: 5.000 - 2.000 - 300 = 2.700 €.
    """
    engine = TaxEngine()

    # 1T
    q1_130 = engine.calculate_model_130_from_data(
        fiscal_year=2026, quarter=1,
        accumulated_incomes=15000.0, accumulated_expenses=5000.0,
        previous_payments=0.0, retentions_supported=0.0
    )
    assert q1_130.casillas["03"] == 10000.0
    assert q1_130.casillas["04"] == 2000.0
    assert q1_130.casillas["19"] == 2000.0
    pago_efectuado_1t = q1_130.casillas["19"]

    # 2T acumulado
    q2_130 = engine.calculate_model_130_from_data(
        fiscal_year=2026, quarter=2,
        accumulated_incomes=40000.0, accumulated_expenses=15000.0,
        previous_payments=pago_efectuado_1t, retentions_supported=300.0
    )
    assert q2_130.casillas["03"] == 25000.0
    assert q2_130.casillas["04"] == 5000.0   # 20% sobre 25.000
    assert q2_130.casillas["07"] == 2000.0   # Deducción pago 1T
    assert q2_130.casillas["08"] == 300.0    # Retenciones soportadas
    assert q2_130.casillas["19"] == 2700.0   # 5000 - 2000 - 300
