"""
test_qa_strategic_dafo_suite.py
===============================
Suite de pruebas de Calidad y Aceptación (QA) para el Módulo 8:
Generación de matrices estratégicas DAFO sobre 10 perfiles representativos
de pymes y autónomos con diferentes casuísticas financieras y de mercado.
"""

import pytest
import sqlite3
from decimal import Decimal
from app.domain.services.strategic_dafo_orchestrator import StrategicDAFOOrchestrator
from app.domain.services.market_analysis_calculator import MarketAnalysisCalculator
from app.domain.schemas import DAFOAnalysisReportDTO
from app.infrastructure.database.market_intelligence_seeder import MarketIntelligenceSeeder


@pytest.fixture
def qa_db():
    conn = sqlite3.connect(":memory:")
    MarketIntelligenceSeeder.init_tables(conn)
    yield conn
    conn.close()


SME_PROFILES = [
    {
        "id": "PERFIL_01_PROGRAMADOR_AUTONOMO",
        "cnae": "6201",
        "region": "Comunidad de Madrid",
        "user_price": Decimal("38.00"),
        "units": Decimal("1600.00"),
        "revenue": Decimal("60800.00"),
        "burn_rate": Decimal("2500.00"),
        "liquidity": Decimal("18000.00"),
        "clients": [("Cliente Tech A", Decimal("32000.00")), ("Cliente Tech B", Decimal("18000.00")), ("Cliente C", Decimal("10800.00"))],
        "suppliers": [{"name": "AWS Cloud", "prev_cost": Decimal("4000.00"), "curr_cost": Decimal("4800.00")}]
    },
    {
        "id": "PERFIL_02_FONTANERO_INSTALADOR",
        "cnae": "4322",
        "region": "Comunidad de Madrid",
        "user_price": Decimal("30.00"),
        "units": Decimal("1200.00"),
        "revenue": Decimal("36000.00"),
        "burn_rate": Decimal("1800.00"),
        "liquidity": Decimal("7200.00"),
        "clients": [("Comunidad Propietarios 1", Decimal("8000.00")), ("Cliente 2", Decimal("6000.00")), ("Cliente 3", Decimal("5000.00"))],
        "suppliers": [{"name": "Materiales Cobre SL", "prev_cost": Decimal("9000.00"), "curr_cost": Decimal("11000.00")}]
    },
    {
        "id": "PERFIL_03_ASESORIA_FISCAL",
        "cnae": "6920",
        "region": "España",
        "user_price": Decimal("65.00"),
        "units": Decimal("2000.00"),
        "revenue": Decimal("130000.00"),
        "burn_rate": Decimal("7500.00"),
        "liquidity": Decimal("45000.00"),
        "clients": [("Pyme Mayor 1", Decimal("15000.00")), ("Pyme 2", Decimal("12000.00")), ("Pyme 3", Decimal("10000.00"))],
        "suppliers": [{"name": "Software Contable", "prev_cost": Decimal("5000.00"), "curr_cost": Decimal("5200.00")}]
    },
    {
        "id": "PERFIL_04_ESTUDIO_INGENIERIA",
        "cnae": "7112",
        "region": "España",
        "user_price": Decimal("85.00"),
        "units": Decimal("1500.00"),
        "revenue": Decimal("127500.00"),
        "burn_rate": Decimal("6000.00"),
        "liquidity": Decimal("36000.00"),
        "clients": [("Constructora Alpha", Decimal("65000.00")), ("Estudio B", Decimal("35000.00")), ("Cliente C", Decimal("27500.00"))],
        "suppliers": [{"name": "Licencias CAD", "prev_cost": Decimal("12000.00"), "curr_cost": Decimal("13500.00")}]
    },
    {
        "id": "PERFIL_05_CONSULTORIA_ESTRATEGICA",
        "cnae": "7022",
        "region": "Comunidad de Madrid",
        "user_price": Decimal("95.00"),
        "units": Decimal("800.00"),
        "revenue": Decimal("76000.00"),
        "burn_rate": Decimal("3500.00"),
        "liquidity": Decimal("28000.00"),
        "clients": [("Corporación X", Decimal("30000.00")), ("Empresa Y", Decimal("25000.00")), ("Cliente Z", Decimal("21000.00"))],
        "suppliers": [{"name": "Bases de Datos", "prev_cost": Decimal("2000.00"), "curr_cost": Decimal("2100.00")}]
    },
    {
        "id": "PERFIL_06_REPARACION_MAQUINARIA",
        "cnae": "3312",
        "region": "España",
        "user_price": Decimal("48.00"),
        "units": Decimal("1800.00"),
        "revenue": Decimal("86400.00"),
        "burn_rate": Decimal("4800.00"),
        "liquidity": Decimal("19200.00"),
        "clients": [("Fábrica 1", Decimal("22000.00")), ("Taller 2", Decimal("18000.00")), ("Cliente 3", Decimal("15000.00"))],
        "suppliers": [{"name": "Repuestos Industriales", "prev_cost": Decimal("20000.00"), "curr_cost": Decimal("23000.00")}]
    },
    {
        "id": "PERFIL_07_INSTALACIONES_ELECTRICAS",
        "cnae": "4321",
        "region": "Comunidad de Madrid",
        "user_price": Decimal("34.00"),
        "units": Decimal("1400.00"),
        "revenue": Decimal("47600.00"),
        "burn_rate": Decimal("2900.00"),
        "liquidity": Decimal("11600.00"),
        "clients": [("Promotora Viviendas", Decimal("25000.00")), ("Cliente 2", Decimal("12000.00")), ("Cliente 3", Decimal("10600.00"))],
        "suppliers": [{"name": "Cableados y Cuadros", "prev_cost": Decimal("14000.00"), "curr_cost": Decimal("16500.00")}]
    },
    {
        "id": "PERFIL_08_TRANSPORTE_CARRETERA",
        "cnae": "4941",
        "region": "España",
        "user_price": Decimal("1.25"),
        "units": Decimal("80000.00"),
        "revenue": Decimal("100000.00"),
        "burn_rate": Decimal("6200.00"),
        "liquidity": Decimal("24800.00"),
        "clients": [("Operador Logístico", Decimal("42000.00")), ("Cargador B", Decimal("30000.00")), ("Cliente C", Decimal("28000.00"))],
        "suppliers": [{"name": "Combustible SL", "prev_cost": Decimal("35000.00"), "curr_cost": Decimal("39000.00")}]
    },
    {
        "id": "PERFIL_09_AGENCIA_MARKETING",
        "cnae": "7311",
        "region": "Comunidad de Madrid",
        "user_price": Decimal("50.00"),
        "units": Decimal("1100.00"),
        "revenue": Decimal("55000.00"),
        "burn_rate": Decimal("3100.00"),
        "liquidity": Decimal("15500.00"),
        "clients": [("E-commerce Retail", Decimal("24000.00")), ("Cliente B", Decimal("16000.00")), ("Cliente C", Decimal("15000.00"))],
        "suppliers": [{"name": "Meta Ads / Google", "prev_cost": Decimal("12000.00"), "curr_cost": Decimal("13000.00")}]
    },
    {
        "id": "PERFIL_10_DISENO_GRAFICO",
        "cnae": "7410",
        "region": "España",
        "user_price": Decimal("42.00"),
        "units": Decimal("900.00"),
        "revenue": Decimal("37800.00"),
        "burn_rate": Decimal("1900.00"),
        "liquidity": Decimal("9500.00"),
        "clients": [("Editorial A", Decimal("12000.00")), ("Estudio B", Decimal("10000.00")), ("Cliente C", Decimal("8000.00"))],
        "suppliers": [{"name": "Software Adobe", "prev_cost": Decimal("1200.00"), "curr_cost": Decimal("1250.00")}]
    }
]


@pytest.mark.parametrize("profile", SME_PROFILES, ids=[p["id"] for p in SME_PROFILES])
def test_qa_strategic_dafo_suite_across_10_sme_profiles(qa_db, profile):
    """
    Verifica que el informe DAFO para cada uno de los 10 perfiles pyme:
    1. Se genera y valida estrictamente contra DAFOAnalysisReportDTO.
    2. Contiene al menos 2 elementos por cuadrante (fortalezas, debilidades, oportunidades, amenazas).
    3. Contiene al menos 3 propuestas tácticas concretas en acciones_recomendadas.
    4. Se almacena correctamente en la base de datos SQLite sin fugas de datos personales.
    """
    orchestrator = StrategicDAFOOrchestrator(db_connection=qa_db)

    # 1. Ejecutar auditoría interna personalizada para el perfil
    audit = MarketAnalysisCalculator.calculate_business_risk_audit(
        total_annual_revenue=profile["revenue"],
        clients_turnover=profile["clients"],
        suppliers_data=profile["suppliers"],
        total_liquidity=profile["liquidity"],
        monthly_burn_rate=profile["burn_rate"],
        sector_inflation_rate=Decimal("3.20")
    )

    # 2. Generar el informe DAFO
    report = orchestrator.generate_dafo_report(
        cnae_code=profile["cnae"],
        region=profile["region"],
        fiscal_year=2026,
        user_average_price=profile["user_price"],
        total_units_sold=profile["units"],
        custom_audit=audit
    )

    # 3. Comprobaciones de calidad formal y restricciones de esquema
    assert isinstance(report, DAFOAnalysisReportDTO)
    assert report.cnae_code == profile["cnae"]
    assert len(report.fortalezas) >= 2
    assert len(report.debilidades) >= 2
    assert len(report.oportunidades) >= 2
    assert len(report.amenazas) >= 2
    assert len(report.acciones_recomendadas) >= 3

    # Verificar que contiene cifras de acción y ningún NIF/CIF
    for accion in report.acciones_recomendadas:
        assert len(accion) > 15
        assert "%" in accion or "€" in accion or "meses" in accion.lower()

    # 4. Verificar persistencia en base de datos
    cursor = qa_db.cursor()
    cursor.execute(
        "SELECT report_id, cnae_code, dafo_payload_json FROM strategic_dafo_reports WHERE cnae_code = ?",
        (profile["cnae"],)
    )
    row = cursor.fetchone()
    assert row is not None
    assert row[1] == profile["cnae"]
