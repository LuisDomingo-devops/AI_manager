"""
market_analysis_calculator.py
=============================
Motor determinista de cálculo financiero y posicionamiento competitivo:
- Benchmarking de precios frente a distribución sectorial empírica (CNAE).
- Posicionamiento en percentiles e interpolación lineal estricta con Decimal.
- Cálculo de margen potencial de incremento de facturación.
- Auditoría de concentración de cartera de clientes (C1, C3) y alertas de riesgo.
- Análisis de riesgo de proveedores y sobrecostes vs inflación sectorial (INE).
- Estimación del runway de tesorería (meses de cobertura).
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Dict, Any, Optional
from app.domain.schemas import (
    SectorBenchmarkDTO,
    BusinessRiskAuditDTO,
    TopClientConcentrationItemDTO,
    TopSupplierRiskItemDTO
)


class MarketAnalysisCalculator:
    """Calculador financiero de inteligencia competitiva y auditoría de riesgos."""

    @classmethod
    def calculate_price_benchmark(
        cls,
        cnae_code: str,
        sector_name: str,
        region: str,
        user_average_price: Decimal,
        p25_price: Decimal,
        p50_price: Decimal,
        p75_price: Decimal,
        average_market_price: Decimal,
        total_units_sold: Decimal = Decimal("0.00")
    ) -> SectorBenchmarkDTO:
        """
        Calcula el posicionamiento competitivo en percentiles y el margen potencial de mejora.
        """
        user_p = Decimal(str(user_average_price)).quantize(Decimal("0.01"))
        p25 = Decimal(str(p25_price)).quantize(Decimal("0.01"))
        p50 = Decimal(str(p50_price)).quantize(Decimal("0.01"))
        p75 = Decimal(str(p75_price)).quantize(Decimal("0.01"))
        avg_m = Decimal(str(average_market_price)).quantize(Decimal("0.01"))
        units = Decimal(str(total_units_sold)).quantize(Decimal("0.01"))

        # 1. Determinación del percentil (0 a 100)
        if p50 <= Decimal("0.00"):
            percentile = 50
        elif user_p <= p25:
            if p25 > Decimal("0.00"):
                ratio = (user_p / p25)
                percentile = int(Decimal("5") + ratio * Decimal("20"))
            else:
                percentile = 15
            percentile = min(33, max(0, percentile))
        elif user_p <= p50:
            diff = p50 - p25
            ratio = (user_p - p25) / diff if diff > Decimal("0.00") else Decimal("0.5")
            percentile = int(Decimal("25") + ratio * Decimal("25"))
            percentile = min(50, max(25, percentile))
        elif user_p <= p75:
            diff = p75 - p50
            ratio = (user_p - p50) / diff if diff > Decimal("0.00") else Decimal("0.5")
            percentile = int(Decimal("50") + ratio * Decimal("25"))
            percentile = min(75, max(50, percentile))
        else:
            diff = p75
            ratio = (user_p - p75) / diff if diff > Decimal("0.00") else Decimal("0.5")
            percentile = int(Decimal("75") + ratio * Decimal("25"))
            percentile = min(100, max(75, percentile))

        # 2. Segmentación de mercado
        if percentile <= 33:
            segment = "Económico"
        elif percentile <= 66:
            segment = "Medio"
        else:
            segment = "Premium"

        # 3. Potencial de incremento de ingresos al equiparar precios a la media
        if user_p < avg_m and units > Decimal("0.00"):
            potential_upside = ((avg_m - user_p) * units).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            potential_upside = Decimal("0.00")

        # 4. Redacción de recomendación táctica
        if segment == "Económico":
            recommendation = (
                f"Sus tarifas se sitúan en el percentil {percentile} ({segment}). "
                f"Existe un margen de mejora estimado de {potential_upside} € si ajusta sus precios hacia la media sectorial de {avg_m} €."
            )
        elif segment == "Medio":
            recommendation = (
                f"Sus tarifas se sitúan en el percentil {percentile} ({segment}). "
                f"Su precio medio ({user_p} €) se alinea con la mediana del sector ({p50} €). Margen competitivo equilibrado."
            )
        else:
            recommendation = (
                f"Sus tarifas se sitúan en el percentil {percentile} ({segment}). "
                f"Posicionamiento de alta gama por encima del percentil 75 ({p75} €). Foco en retención y calidad percibida."
            )

        return SectorBenchmarkDTO(
            cnae_code=cnae_code,
            sector_name=sector_name,
            region=region,
            average_market_price=avg_m,
            user_average_price=user_p,
            price_position_percentile=percentile,
            positioning_segment=segment,
            potential_revenue_upside=potential_upside,
            recommendation=recommendation
        )

    @classmethod
    def calculate_business_risk_audit(
        cls,
        total_annual_revenue: Decimal,
        clients_turnover: List[Tuple[str, Decimal]],
        suppliers_data: List[Dict[str, Any]],
        total_liquidity: Decimal,
        monthly_burn_rate: Decimal,
        sector_inflation_rate: Decimal = Decimal("3.00")
    ) -> BusinessRiskAuditDTO:
        """
        Audita el riesgo de concentración de clientes, la inflación de costes en compras
        y la cobertura de meses de tesorería (runway).
        """
        rev = Decimal(str(total_annual_revenue)).quantize(Decimal("0.01"))
        liq = Decimal(str(total_liquidity)).quantize(Decimal("0.01"))
        burn = Decimal(str(monthly_burn_rate)).quantize(Decimal("0.01"))
        inflation = Decimal(str(sector_inflation_rate)).quantize(Decimal("0.01"))

        # 1. Concentración de Clientes
        sorted_clients = sorted(clients_turnover, key=lambda x: x[1], reverse=True)
        top_clients_dtos: List[TopClientConcentrationItemDTO] = []
        top_3_sum = Decimal("0.00")
        top_1_ratio = Decimal("0.00")

        for idx, (label, amount) in enumerate(sorted_clients[:3]):
            amt = Decimal(str(amount)).quantize(Decimal("0.01"))
            pct = (amt / rev * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if rev > Decimal("0.00") else Decimal("0.00")
            if idx == 0:
                top_1_ratio = pct
            top_3_sum += amt
            top_clients_dtos.append(
                TopClientConcentrationItemDTO(
                    client_label=label,
                    annual_turnover=amt,
                    concentration_percentage=pct
                )
            )

        c3_ratio = (top_3_sum / rev * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if rev > Decimal("0.00") else Decimal("0.00")

        # Alerta crítica: Un cliente supera el 40% o Top 3 supera el 70%
        high_concentration = bool(top_1_ratio >= Decimal("40.00") or c3_ratio >= Decimal("70.00"))

        # 2. Riesgo de Proveedores
        supplier_dtos: List[TopSupplierRiskItemDTO] = []
        total_cost_increase_pct = Decimal("0.00")

        for s in suppliers_data:
            label = s.get("name", "Proveedor")
            prev_c = Decimal(str(s.get("prev_cost", "0.00"))).quantize(Decimal("0.01"))
            curr_c = Decimal(str(s.get("curr_cost", "0.00"))).quantize(Decimal("0.01"))
            if prev_c > Decimal("0.00"):
                diff_pct = ((curr_c - prev_c) / prev_c * Decimal("100.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                diff_pct = Decimal("0.00")

            exceeds = bool(diff_pct > inflation)
            total_cost_increase_pct += diff_pct

            supplier_dtos.append(
                TopSupplierRiskItemDTO(
                    supplier_label=label,
                    current_year_cost=curr_c,
                    previous_year_cost=prev_c,
                    cost_increase_rate=diff_pct,
                    exceeds_sector_inflation=exceeds
                )
            )

        avg_supplier_increase = (
            (total_cost_increase_pct / Decimal(len(suppliers_data))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if suppliers_data else Decimal("0.00")
        )

        # 3. Cálculo de Runway de Tesorería (meses redondeado a 1 decimal)
        if burn <= Decimal("0.00"):
            runway = Decimal("999.0")
        else:
            runway = (liq / burn).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)

        return BusinessRiskAuditDTO(
            client_concentration_ratio=c3_ratio,
            top_single_client_ratio=top_1_ratio,
            high_concentration_alert=high_concentration,
            top_clients=top_clients_dtos,
            supplier_cost_increase_rate=avg_supplier_increase,
            top_risk_suppliers=supplier_dtos,
            runway_months=runway,
            monthly_burn_rate=burn,
            available_liquidity=liq
        )
