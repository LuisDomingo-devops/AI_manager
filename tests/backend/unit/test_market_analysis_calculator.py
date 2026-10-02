"""
test_market_analysis_calculator.py
==================================
Tests unitarios (TDD) para el calculador financiero de inteligencia de mercado:
- Cálculo de percentil de precios sectoriales y segmentación (Económico, Medio, Premium).
- Cálculo exacto con Decimal del margen de mejora potencial de facturación.
- Índice de concentración de clientes (C1, C3) y activación de alerta (>40%).
- Variación interanual de costes de proveedores frente a inflación sectorial.
- Ratio de cobertura de tesorería y meses de supervivencia (runway).
"""

import pytest
from decimal import Decimal
from app.domain.services.market_analysis_calculator import MarketAnalysisCalculator


def test_price_benchmark_percentile_economic_segment():
    """Valida el cálculo de percentil y segmentación para tarifas por debajo del percentil 25."""
    # Distribución sectorial: p25=40.00, p50=55.00, p75=75.00, average=58.00
    benchmark = MarketAnalysisCalculator.calculate_price_benchmark(
        cnae_code="6201",
        sector_name="Programación",
        region="Madrid",
        user_average_price=Decimal("35.00"),
        p25_price=Decimal("40.00"),
        p50_price=Decimal("55.00"),
        p75_price=Decimal("75.00"),
        average_market_price=Decimal("58.00"),
        total_units_sold=Decimal("200.00")
    )

    assert benchmark.cnae_code == "6201"
    assert benchmark.positioning_segment == "Económico"
    assert 0 <= benchmark.price_position_percentile <= 33
    assert benchmark.user_average_price == Decimal("35.00")
    assert benchmark.average_market_price == Decimal("58.00")
    # Margen de mejora: (58.00 - 35.00) * 200 = 4600.00 €
    assert benchmark.potential_revenue_upside == Decimal("4600.00")
    assert "percentil" in benchmark.recommendation.lower()


def test_price_benchmark_percentile_medium_and_premium_segment():
    """Valida la clasificación en segmento Medio y Premium con potencial cero si supera la media."""
    # Segmento Medio
    bench_mid = MarketAnalysisCalculator.calculate_price_benchmark(
        cnae_code="6201",
        sector_name="Programación",
        region="Madrid",
        user_average_price=Decimal("55.00"),
        p25_price=Decimal("40.00"),
        p50_price=Decimal("55.00"),
        p75_price=Decimal("75.00"),
        average_market_price=Decimal("58.00"),
        total_units_sold=Decimal("100.00")
    )
    assert bench_mid.positioning_segment == "Medio"
    assert 34 <= bench_mid.price_position_percentile <= 66

    # Segmento Premium (sin potencial de subida hacia la media)
    bench_premium = MarketAnalysisCalculator.calculate_price_benchmark(
        cnae_code="6201",
        sector_name="Programación",
        region="Madrid",
        user_average_price=Decimal("85.00"),
        p25_price=Decimal("40.00"),
        p50_price=Decimal("55.00"),
        p75_price=Decimal("75.00"),
        average_market_price=Decimal("58.00"),
        total_units_sold=Decimal("100.00")
    )
    assert bench_premium.positioning_segment == "Premium"
    assert bench_premium.price_position_percentile >= 67
    assert bench_premium.potential_revenue_upside == Decimal("0.00")


def test_client_concentration_alert_trigger():
    """Valida la activación de la alerta de alta concentración si un cliente supera el 40%."""
    # Facturación total 100.000 €: Cliente Alpha = 45.000 (45%), Cliente Beta = 20.000 (20%), Cliente Gamma = 10.000 (10%)
    clients_turnover = [
        ("Cliente Alpha", Decimal("45000.00")),
        ("Cliente Beta", Decimal("20000.00")),
        ("Cliente Gamma", Decimal("10000.00")),
        ("Cliente Delta", Decimal("15000.00")),
        ("Cliente Epsilon", Decimal("10000.00")),
    ]
    total_revenue = Decimal("100000.00")

    audit = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=total_revenue,
        clients_turnover=clients_turnover,
        suppliers_data=[],
        total_liquidity=Decimal("20000.00"),
        monthly_burn_rate=Decimal("4000.00"),
        sector_inflation_rate=Decimal("3.20")
    )

    assert audit.top_single_client_ratio == Decimal("45.00")
    # Top 3: 45000 + 20000 + 15000 = 80000 (80.00%)
    assert audit.client_concentration_ratio == Decimal("80.00")
    assert audit.high_concentration_alert is True
    assert len(audit.top_clients) == 3
    assert audit.top_clients[0].concentration_percentage == Decimal("45.00")


def test_client_concentration_no_alert_when_diversified():
    """Valida que no salte la alerta si el cliente mayoritario está por debajo del 40% y top 3 < 70%."""
    clients_turnover = [
        ("Cliente A", Decimal("25000.00")),
        ("Cliente B", Decimal("20000.00")),
        ("Cliente C", Decimal("15000.00")),
        ("Cliente D", Decimal("10000.00")),
        ("Cliente E", Decimal("10000.00")),
        ("Cliente F", Decimal("10000.00")),
        ("Cliente G", Decimal("10000.00")),
    ]
    total_revenue = Decimal("100000.00")

    audit = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=total_revenue,
        clients_turnover=clients_turnover,
        suppliers_data=[],
        total_liquidity=Decimal("15000.00"),
        monthly_burn_rate=Decimal("3000.00"),
        sector_inflation_rate=Decimal("3.20")
    )

    assert audit.top_single_client_ratio == Decimal("25.00")
    assert audit.client_concentration_ratio == Decimal("60.00")
    assert audit.high_concentration_alert is False


def test_supplier_cost_increase_vs_sector_inflation():
    """Valida la detección de incrementos de costes en proveedores que exceden la inflación del sector."""
    suppliers_data = [
        # Proveedor 1: coste sube de 10.000 a 12.000 (+20% vs inflación 3.2%)
        {"name": "Proveedor Cloud", "prev_cost": Decimal("10000.00"), "curr_cost": Decimal("12000.00")},
        # Proveedor 2: coste sube de 5.000 a 5.100 (+2.0% vs inflación 3.2%)
        {"name": "Proveedor Oficina", "prev_cost": Decimal("5000.00"), "curr_cost": Decimal("5100.00")}
    ]

    audit = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=Decimal("50000.00"),
        clients_turnover=[("Cliente 1", Decimal("50000.00"))],
        suppliers_data=suppliers_data,
        total_liquidity=Decimal("10000.00"),
        monthly_burn_rate=Decimal("2000.00"),
        sector_inflation_rate=Decimal("3.20")
    )

    assert len(audit.top_risk_suppliers) == 2
    prov_cloud = audit.top_risk_suppliers[0]
    assert prov_cloud.cost_increase_rate == Decimal("20.00")
    assert prov_cloud.exceeds_sector_inflation is True

    prov_ofi = audit.top_risk_suppliers[1]
    assert prov_ofi.cost_increase_rate == Decimal("2.00")
    assert prov_ofi.exceeds_sector_inflation is False


def test_runway_months_calculation():
    """Valida el cálculo de meses de cobertura de tesorería con redondeo a 1 decimal."""
    # Tesorería 25.400 € / Gasto mensual 4.200 € = 6.0476... -> 6.0 meses
    audit = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=Decimal("100000.00"),
        clients_turnover=[],
        suppliers_data=[],
        total_liquidity=Decimal("25400.00"),
        monthly_burn_rate=Decimal("4200.00"),
        sector_inflation_rate=Decimal("3.00")
    )
    assert audit.runway_months == Decimal("6.0")

    # Si el burn rate es 0 (no hay gasto mensual fijo), el runway es 999.0
    audit_no_burn = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=Decimal("100000.00"),
        clients_turnover=[],
        suppliers_data=[],
        total_liquidity=Decimal("25400.00"),
        monthly_burn_rate=Decimal("0.00"),
        sector_inflation_rate=Decimal("3.00")
    )
    assert audit_no_burn.runway_months == Decimal("999.0")
