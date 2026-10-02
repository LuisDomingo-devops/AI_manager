"""
test_tax_engine_model_calculations.py
======================================
Tests unitarios TDD para el cálculo determinista y asignación canónica de casillas oficiales
de los modelos tributarios de la AEAT (303, 130, 111, 115 y 390).
Conforme a la Orden EHA/3786/2008, Orden HFP/1395/2023 y Orden EHA/3202/2008.
"""
import pytest
from app.domain.services.tax_engine import TaxEngine
from app.domain.services.annual_tax_service import AnnualTaxService
from app.domain.models.billing import (
    Model303ResultDTO,
    Model130ResultDTO,
    Model111ResultDTO,
    Model115ResultDTO,
    Model390ResultDTO
)


def test_calculate_model_303_canonical_casillas_mapping():
    """
    Verifica la asignación canónica oficial del Modelo 303 eliminando la contradicción de casillas:
    - Base 21% -> Casilla 01, Tipo 21.0 -> Casilla 02, Cuota 21% -> Casilla 03.
    - Base 10% -> Casilla 04, Tipo 10.0 -> Casilla 05, Cuota 10% -> Casilla 06.
    - Base 4% -> Casilla 07, Tipo 4.0 -> Casilla 08, Cuota 4% -> Casilla 09.
    - Deducible operaciones interiores corrientes -> Casillas 28 y 29.
    - Deducible bienes de inversión -> Casillas 30 y 31.
    - Compensación periodos anteriores -> Casilla 110.
    - Resultado autoliquidación -> Casilla 71.
    """
    engine = TaxEngine()

    sales = [
        {"base": 1000.0, "vat_rate": 21.0, "tax": 210.0},
        {"base": 500.0, "vat_rate": 10.0, "tax": 50.0},
        {"base": 200.0, "vat_rate": 4.0, "tax": 8.0},
    ]

    purchases = [
        {"base": 400.0, "vat_rate": 21.0, "tax": 84.0, "is_investment": False},
        {"base": 1000.0, "vat_rate": 21.0, "tax": 210.0, "is_investment": True},
    ]

    res: Model303ResultDTO = engine.calculate_model_303_from_data(
        fiscal_year=2026,
        quarter=1,
        sales=sales,
        purchases=purchases,
        prorrata_pct=100.0,
        compensacion_periodos_anteriores=50.0
    )

    assert isinstance(res, Model303ResultDTO)
    # Devengado
    assert res.casillas["01"] == 200.0    # Base 4%
    assert res.casillas["02"] == 4.0      # Tipo 4%
    assert res.casillas["03"] == 8.0      # Cuota 4%
    assert res.casillas["04"] == 500.0    # Base 10%
    assert res.casillas["05"] == 10.0     # Tipo 10%
    assert res.casillas["06"] == 50.0     # Cuota 10%
    assert res.casillas["07"] == 1000.0   # Base 21%
    assert res.casillas["08"] == 21.0     # Tipo 21%
    assert res.casillas["09"] == 210.0    # Cuota 21%
    assert res.casillas["27"] == 268.0    # Total devengado (210 + 50 + 8)

    # Deducible
    assert res.casillas["28"] == 400.0    # Base corriente
    assert res.casillas["29"] == 84.0     # Cuota corriente
    assert res.casillas["30"] == 1000.0   # Base inversión
    assert res.casillas["31"] == 210.0    # Cuota inversión
    assert res.casillas["37"] == 294.0    # Total deducible (84 + 210)

    # Liquidación
    assert res.casillas["46"] == -26.0    # Diferencia (268 - 294)
    assert res.casillas["110"] == 50.0    # Saldo previo a compensar
    assert res.casillas["71"] == -76.0    # Resultado final (-26 - 50)
    assert res.resultado_autoliquidacion == -76.0


def test_calculate_model_303_with_prorrata():
    """Valida la aplicación de la regla de prorrata sobre las cuotas deducibles."""
    engine = TaxEngine()
    sales = [{"base": 1000.0, "vat_rate": 21.0, "tax": 210.0}]
    purchases = [{"base": 1000.0, "vat_rate": 21.0, "tax": 210.0, "is_investment": False}]

    res = engine.calculate_model_303_from_data(
        fiscal_year=2026,
        quarter=2,
        sales=sales,
        purchases=purchases,
        prorrata_pct=50.0,
        compensacion_periodos_anteriores=0.0
    )

    # Con 50% de prorrata: deducible es 210 * 0.50 = 105.00
    assert res.casillas["37"] == 105.0
    assert res.casillas["46"] == 105.0    # 210 - 105
    assert res.casillas["71"] == 105.0


def test_calculate_model_130_cumulative():
    """Valida el cálculo fraccionado acumulativo del IRPF (Modelo 130)."""
    engine = TaxEngine()

    res: Model130ResultDTO = engine.calculate_model_130_from_data(
        fiscal_year=2026,
        quarter=2,
        accumulated_incomes=30000.0,
        accumulated_expenses=12000.0,
        previous_payments=1500.0,
        retentions_supported=500.0,
        deduction_art_80_bis=0.0
    )

    assert isinstance(res, Model130ResultDTO)
    assert res.casillas["01"] == 30000.0
    assert res.casillas["02"] == 12000.0
    assert res.casillas["03"] == 18000.0  # Rendimiento neto
    assert res.casillas["04"] == 3600.0   # 20% de 18.000
    assert res.casillas["07"] == 1500.0   # Pagos 1T
    assert res.casillas["08"] == 500.0    # Retenciones soportadas
    assert res.casillas["19"] == 1600.0   # 3600 - 1500 - 500
    assert res.casilla_19_resultado_ingresar == 1600.0


def test_calculate_model_111_retentions():
    """Valida el cómputo de retenciones de trabajo y profesionales (Modelo 111)."""
    engine = TaxEngine()

    withholdings_work = [
        {"base": 2000.0, "amount": 300.0},
        {"base": 1800.0, "amount": 250.0},
    ]
    withholdings_prof = [
        {"base": 1000.0, "amount": 150.0},
    ]

    res: Model111ResultDTO = engine.calculate_model_111_from_data(
        fiscal_year=2026,
        quarter=1,
        work_withholdings=withholdings_work,
        prof_withholdings=withholdings_prof
    )

    assert isinstance(res, Model111ResultDTO)
    assert res.perceptores_trabajo == 2
    assert res.base_trabajo == 3800.0
    assert res.retenciones_trabajo == 550.0
    assert res.perceptores_profesionales == 1
    assert res.base_profesionales == 1000.0
    assert res.retenciones_profesionales == 150.0
    assert res.resultado_total == 700.0
    assert res.casillas["28"] == 700.0


def test_calculate_model_115_urban_rentals():
    """Valida el cálculo de retenciones por alquileres de inmuebles (Modelo 115 - 19%)."""
    engine = TaxEngine()

    rental_withholdings = [
        {"base": 1200.0, "amount": 228.0},
        {"base": 800.0, "amount": 152.0},
    ]

    res: Model115ResultDTO = engine.calculate_model_115_from_data(
        fiscal_year=2026,
        quarter=3,
        rental_withholdings=rental_withholdings
    )

    assert isinstance(res, Model115ResultDTO)
    assert res.numero_arrendadores == 2
    assert res.base_arrendamientos == 2000.0
    assert res.retenciones_arrendamientos == 380.0
    assert res.resultado_a_ingresar == 380.0
    assert res.casillas["05"] == 380.0


def test_calculate_model_390_annual_summary():
    """Valida la conciliación anual acumulada del Modelo 390 cruzando los 4 trimestres."""
    service = AnnualTaxService()

    q1 = Model303ResultDTO(
        fiscal_year=2026, quarter=1,
        base_general_21=10000.0, cuota_general_21=2100.0,
        base_deducible_corriente=4000.0, iva_deducible_corriente=840.0,
        total_cuota_devengada=2100.0, total_iva_deducible=840.0,
        resultado_autoliquidacion=1260.0, casillas={}
    )
    q2 = Model303ResultDTO(
        fiscal_year=2026, quarter=2,
        base_general_21=15000.0, cuota_general_21=3150.0,
        base_deducible_corriente=6000.0, iva_deducible_corriente=1260.0,
        total_cuota_devengada=3150.0, total_iva_deducible=1260.0,
        resultado_autoliquidacion=1890.0, casillas={}
    )
    q3 = Model303ResultDTO(
        fiscal_year=2026, quarter=3,
        base_general_21=8000.0, cuota_general_21=1680.0,
        base_deducible_corriente=3000.0, iva_deducible_corriente=630.0,
        total_cuota_devengada=1680.0, total_iva_deducible=630.0,
        resultado_autoliquidacion=1050.0, casillas={}
    )
    q4 = Model303ResultDTO(
        fiscal_year=2026, quarter=4,
        base_general_21=12000.0, cuota_general_21=2520.0,
        base_deducible_corriente=5000.0, iva_deducible_corriente=1050.0,
        total_cuota_devengada=2520.0, total_iva_deducible=1050.0,
        resultado_autoliquidacion=1470.0, casillas={}
    )

    res: Model390ResultDTO = service.calculate_model_390(
        fiscal_year=2026,
        quarterly_declarations=[q1, q2, q3, q4]
    )

    assert isinstance(res, Model390ResultDTO)
    assert res.fiscal_year == 2026
    assert res.total_base_devengada_21 == 45000.0  # 10k + 15k + 8k + 12k
    assert res.total_cuota_devengada_21 == 9450.0
    assert res.total_base_deducible_corriente == 18000.0
    assert res.total_cuota_deducible_corriente == 3780.0
    assert res.volumen_total_operaciones == 45000.0
    assert res.resultado_anual_declaracion == 5670.0
