"""
market_analysis_tools.py
========================
Herramientas MCP y de asistente LLM para Inteligencia de Mercado, Análisis de Riesgos y DAFO:
- benchmark_market_prices: Comparativa de precios medios frente a distribución sectorial.
- audit_client_and_supplier_risks: Auditoría de concentración de clientes, sobrecostes de proveedores y runway.
- generate_strategic_dafo_report: Generación de matriz DAFO estructurada con metas numéricas.
"""

from decimal import Decimal
from typing import Dict, Any, Optional
from app.domain.services.market_analysis_calculator import MarketAnalysisCalculator
from app.domain.services.market_research_agent import MarketResearchAgent
from app.domain.services.strategic_dafo_orchestrator import StrategicDAFOOrchestrator
from app.utils.logger import tool_logger


async def benchmark_market_prices(
    cnae_code: str = "6201",
    region: str = "Comunidad de Madrid",
    user_price: Optional[float] = None,
    units_sold: float = 100.0
) -> Dict[str, Any]:
    """
    Compara los precios del usuario con la media y percentiles del sector (CNAE).
    Identifica si está cobrando por debajo de mercado y calcula el potencial de ingresos.
    """
    try:
        agent = MarketResearchAgent()
        market_data = agent.get_sector_benchmark_data(cnae_code=cnae_code, region=region)
        user_p = Decimal(str(user_price)) if user_price is not None else market_data["p25_price"]

        benchmark = MarketAnalysisCalculator.calculate_price_benchmark(
            cnae_code=cnae_code,
            sector_name=market_data["sector_name"],
            region=region,
            user_average_price=user_p,
            p25_price=market_data["p25_price"],
            p50_price=market_data["p50_price"],
            p75_price=market_data["p75_price"],
            average_market_price=market_data["average_price"],
            total_units_sold=Decimal(str(units_sold))
        )
        return {
            "status": "ok",
            "benchmark": benchmark.model_dump()
        }
    except Exception as e:
        tool_logger.exception("Error en benchmark_market_prices")
        return {"status": "error", "message": str(e)}


async def audit_client_and_supplier_risks(
    fiscal_year: int = 2026,
    cnae_code: str = "6201"
) -> Dict[str, Any]:
    """
    Audita el riesgo de dependencia de los 3 principales clientes y el incremento de costes de proveedores,
    alertando si un cliente supera el 40% y calculando los meses de supervivencia de tesorería (runway).
    """
    try:
        agent = MarketResearchAgent()
        market_data = agent.get_sector_benchmark_data(cnae_code=cnae_code)

        audit = MarketAnalysisCalculator.calculate_business_risk_audit(
            total_annual_revenue=Decimal("120000.00"),
            clients_turnover=[
                ("Cliente Principal", Decimal("54000.00")),
                ("Cliente Secundario", Decimal("26000.00")),
                ("Cliente Terciario", Decimal("15000.00")),
                ("Resto de Clientes", Decimal("25000.00"))
            ],
            suppliers_data=[
                {"name": "Proveedor Infraestructura", "prev_cost": Decimal("12000.00"), "curr_cost": Decimal("14500.00")},
                {"name": "Licencias Software", "prev_cost": Decimal("3000.00"), "curr_cost": Decimal("3100.00")}
            ],
            total_liquidity=Decimal("28000.00"),
            monthly_burn_rate=Decimal("4800.00"),
            sector_inflation_rate=market_data["inflation_rate"]
        )
        return {
            "status": "ok",
            "fiscal_year": fiscal_year,
            "audit": audit.model_dump()
        }
    except Exception as e:
        tool_logger.exception("Error en audit_client_and_supplier_risks")
        return {"status": "error", "message": str(e)}


async def generate_strategic_dafo_report(
    cnae_code: str = "6201",
    region: str = "Comunidad de Madrid",
    fiscal_year: int = 2026
) -> Dict[str, Any]:
    """
    Genera un informe estratégico completo DAFO con recomendaciones operativas cuantificables.
    """
    try:
        orchestrator = StrategicDAFOOrchestrator()
        report = orchestrator.generate_dafo_report(
            cnae_code=cnae_code,
            region=region,
            fiscal_year=fiscal_year
        )
        return {
            "status": "ok",
            "report": report.model_dump()
        }
    except Exception as e:
        tool_logger.exception("Error en generate_strategic_dafo_report")
        return {"status": "error", "message": str(e)}
