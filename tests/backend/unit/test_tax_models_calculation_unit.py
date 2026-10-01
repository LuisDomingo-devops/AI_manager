"""
Test Unitario para Cálculo de Modelos Tributarios (User Story 3: Modelos Fiscales Oficiales).
Valida casillas exactas del Modelo 303 (desglose 4%, 10%, 21% y prorrata) y Modelo 130 (acumulado anual IRPF).
"""

import pytest
from app.domain.services.tax_engine import TaxEngine
from app.domain.models.billing import Model303ResultDTO, Model130ResultDTO


def test_calculate_model_303_breakdown_and_prorrata():
    """Valida el cálculo exacto del Modelo 303 con tipos desglosados y prorrata general."""
    engine = TaxEngine()
    
    # Datos de prueba para un trimestre:
    # Ventas: 1000€ al 21% (IVA 210€), 500€ al 10% (IVA 50€), 200€ al 4% (IVA 8€)
    sales = [
        {"base": 1000.0, "vat_rate": 21.0, "tax": 210.0},
        {"base": 500.0, "vat_rate": 10.0, "tax": 50.0},
        {"base": 200.0, "vat_rate": 4.0, "tax": 8.0}
    ]
    # Compras: 800€ con IVA deducible de 168€ (al 21%)
    purchases = [
        {"base": 800.0, "vat_rate": 21.0, "tax": 168.0, "is_investment": False}
    ]
    
    # 1. Sin prorrata (100%)
    res_100: Model303ResultDTO = engine.calculate_model_303_from_data(
        fiscal_year=2026,
        quarter=1,
        sales=sales,
        purchases=purchases,
        prorrata_pct=100.0
    )
    
    assert res_100.base_general_21 == 1000.0
    assert res_100.cuota_general_21 == 210.0
    assert res_100.base_reducido_10 == 500.0
    assert res_100.cuota_reducido_10 == 50.0
    assert res_100.base_superreducido_4 == 200.0
    assert res_100.cuota_superreducido_4 == 8.0
    assert res_100.total_cuota_devengada == 268.0
    
    assert res_100.iva_deducible_corriente == 168.0
    assert res_100.total_iva_deducible == 168.0
    assert res_100.resultado_autoliquidacion == 100.0  # 268.0 - 168.0
    
    # Comprobar numeración de casillas oficiales AEAT
    assert res_100.casillas["01"] == 200.0   # Base 4%
    assert res_100.casillas["03"] == 8.0     # Cuota 4%
    assert res_100.casillas["04"] == 500.0   # Base 10%
    assert res_100.casillas["06"] == 50.0    # Cuota 10%
    assert res_100.casillas["07"] == 1000.0  # Base 21%
    assert res_100.casillas["09"] == 210.0   # Cuota 21%
    assert res_100.casillas["27"] == 268.0   # Total cuota devengada
    assert res_100.casillas["28"] == 800.0   # Base deducible
    assert res_100.casillas["29"] == 168.0   # Cuota deducible
    assert res_100.casillas["46"] == 100.0   # Resultado

    # 2. Con prorrata del 75%
    res_75: Model303ResultDTO = engine.calculate_model_303_from_data(
        fiscal_year=2026,
        quarter=1,
        sales=sales,
        purchases=purchases,
        prorrata_pct=75.0
    )
    assert res_75.prorrata_pct == 75.0
    # Cuota deducible aplicable = 168.0 * 0.75 = 126.0
    assert res_75.total_iva_deducible == 126.0
    assert res_75.resultado_autoliquidacion == 142.0  # 268.0 - 126.0


def test_calculate_model_130_cumulative_irpf():
    """Valida el cálculo del Modelo 130 acumulativo anual conforme al Art. 109 RIRPF."""
    engine = TaxEngine()
    
    # Trimestre 1:
    # Ingresos: 10,000 €, Gastos: 4,000 € -> Rendimiento: 6,000 € -> 20%: 1,200 €
    # Pagos anteriores: 0 € -> A ingresar Q1: 1,200 €
    res_q1: Model130ResultDTO = engine.calculate_model_130_from_data(
        fiscal_year=2026,
        quarter=1,
        accumulated_incomes=10000.0,
        accumulated_expenses=4000.0,
        previous_payments=0.0
    )
    assert res_q1.casilla_01_ingresos_acumulados == 10000.0
    assert res_q1.casilla_02_gastos_acumulados == 4000.0
    assert res_q1.casilla_03_rendimiento_neto == 6000.0
    assert res_q1.casilla_04_pago_fraccionado_previo == 1200.0
    assert res_q1.casilla_07_pagos_anteriores == 0.0
    assert res_q1.casilla_19_resultado_ingresar == 1200.0
    
    # Trimestre 2 (Acumulado desde 1 de Enero):
    # Ingresos acumulados Q1+Q2: 25,000 €, Gastos acumulados Q1+Q2: 10,000 €
    # Rendimiento acumulado: 15,000 € -> 20%: 3,000 €
    # Casilla 07 (Pagos trimestres anteriores): 1,200 €
    # Casilla 19 (A ingresar Q2): 3,000 - 1,200 = 1,800 €
    res_q2: Model130ResultDTO = engine.calculate_model_130_from_data(
        fiscal_year=2026,
        quarter=2,
        accumulated_incomes=25000.0,
        accumulated_expenses=10000.0,
        previous_payments=1200.0
    )
    assert res_q2.casilla_01_ingresos_acumulados == 25000.0
    assert res_q2.casilla_02_gastos_acumulados == 10000.0
    assert res_q2.casilla_03_rendimiento_neto == 15000.0
    assert res_q2.casilla_04_pago_fraccionado_previo == 3000.0
    assert res_q2.casilla_07_pagos_anteriores == 1200.0
    assert res_q2.casilla_19_resultado_ingresar == 1800.0


def test_calculate_withholdings_models_111_and_115():
    """Valida el cálculo de retenciones practicadas para Modelos 111 y 115."""
    engine = TaxEngine()
    
    # Retenciones nóminas y profesionales (Modelo 111)
    withholdings_111 = [
        {"type": "professional", "base": 2000.0, "rate": 15.0, "amount": 300.0},
        {"type": "payroll", "base": 1500.0, "rate": 10.0, "amount": 150.0}
    ]
    res_111 = engine.calculate_model_111(2026, 1, withholdings_111)
    assert res_111["total_perceptores"] == 2
    assert res_111["total_bases"] == 3500.0
    assert res_111["total_retenciones"] == 450.0

    # Retenciones arrendamientos (Modelo 115)
    withholdings_115 = [
        {"type": "rental", "base": 1000.0, "rate": 19.0, "amount": 190.0}
    ]
    res_115 = engine.calculate_model_115(2026, 1, withholdings_115)
    assert res_115["total_arrendadores"] == 1
    assert res_115["total_bases"] == 1000.0
    assert res_115["total_retenciones"] == 190.0
