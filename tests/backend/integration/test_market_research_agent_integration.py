"""
test_market_research_agent_integration.py
=========================================
Tests de integración para el agente de prospección ética de mercado:
- Verificación del cumplimiento del Principio Constitucional V: uso exclusivo de Mozilla Firefox.
- Rechazo explícito de cualquier intento de utilizar Google Chrome o Chromium.
- Interceptación y bloqueo de seguridad RGPD ante filtración de NIFs/CIFs.
- Ciclo de vida de la caché SQLite con TTL de 30 días.
"""

import pytest
import sqlite3
from decimal import Decimal
from unittest.mock import patch, MagicMock
from app.domain.services.market_research_agent import MarketResearchAgent
from app.domain.services.egress_anonymization_gateway import RGPDViolationError
from app.domain.exceptions import FirefoxFilingError
from app.infrastructure.database.market_intelligence_seeder import MarketIntelligenceSeeder


@pytest.fixture
def test_db():
    conn = sqlite3.connect(":memory:")
    MarketIntelligenceSeeder.init_tables(conn)
    yield conn
    conn.close()


def test_egress_gateway_blocks_nif_in_external_query():
    """Comprueba que si se intenta ejecutar una búsqueda con NIF, el gateway bloquea la llamada."""
    agent = MarketResearchAgent()
    # NIF ficticio con dígito de control correcto (12345678Z)
    with pytest.raises(RGPDViolationError) as exc_info:
        agent.execute_market_research(
            cnae_code="6201",
            region="Madrid",
            search_query="Tarifas de la empresa con NIF 12345678Z en Madrid"
        )
    assert "Violación del RGPD" in str(exc_info.value)
    assert any("12345678Z" in entity for entity in exc_info.value.detected_entities)


def test_browser_policy_enforces_firefox_only():
    """Comprueba que cualquier intento de usar Chrome lanza FirefoxFilingError."""
    agent = MarketResearchAgent()
    with pytest.raises(FirefoxFilingError) as exc_info:
        agent.fetch_live_market_data(
            cnae_code="6201",
            region="Madrid",
            browser_type="chrome"
        )
    assert "Google Chrome está estrictamente prohibido" in str(exc_info.value)

    with pytest.raises(FirefoxFilingError):
        agent.fetch_live_market_data(
            cnae_code="6201",
            region="Madrid",
            browser_type="chromium"
        )


def test_market_benchmarks_cache_hit_avoids_browser(test_db):
    """Comprueba que si los datos ya están en la caché SQLite, se devuelven sin abrir el navegador."""
    # Pre-cargar dato en caché SQLite
    cursor = test_db.cursor()
    cursor.execute("""
        INSERT INTO market_sector_benchmarks_cache 
        (cnae_code, region, sector_name, p25_price, p50_price, p75_price, average_price, inflation_rate, source, ttl_days)
        VALUES ('6201', 'Comunidad de Madrid', 'Programación', '40.00', '55.00', '75.00', '58.00', '3.20', 'TEST_CACHE', 30)
    """)
    test_db.commit()

    agent = MarketResearchAgent(db_connection=test_db)
    
    # Debe resolver directamente desde la base de datos sin invocar a Playwright
    data = agent.get_sector_benchmark_data(cnae_code="6201", region="Comunidad de Madrid")

    assert data is not None
    assert data["source"] == "TEST_CACHE"
    assert Decimal(str(data["average_price"])) == Decimal("58.00")
    assert Decimal(str(data["p50_price"])) == Decimal("55.00")


def test_market_benchmarks_cache_miss_populates_db(test_db):
    """Comprueba que cuando no hay datos en caché, se consulta el catálogo o simulación Firefox y se guarda."""
    agent = MarketResearchAgent(db_connection=test_db)

    # Simular extracción exitosa de tarifas con Firefox
    simulated_scraped_data = {
        "cnae_code": "4322",
        "region": "Comunidad de Madrid",
        "sector_name": "Fontanería y Climatización",
        "p25_price": "32.00",
        "p50_price": "42.00",
        "p75_price": "55.00",
        "average_price": "44.00",
        "inflation_rate": "3.80",
        "source": "FIREFOX_SCRAPE"
    }

    with patch.object(agent, "fetch_live_market_data", return_value=simulated_scraped_data):
        data = agent.get_sector_benchmark_data(cnae_code="4322", region="Comunidad de Madrid")

    assert data["source"] == "FIREFOX_SCRAPE"
    assert Decimal(str(data["average_price"])) == Decimal("44.00")

    # Verificar que quedó persistido en test_db
    cursor = test_db.cursor()
    cursor.execute("SELECT source, average_price FROM market_sector_benchmarks_cache WHERE cnae_code = '4322'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "FIREFOX_SCRAPE"
    assert row[1] == "44.00"
