"""
Test Unitario para PGC Seeder y Motor de Amortizaciones (User Story 4: Contabilidad PGC Pymes).
Valida integridad del catálogo de cuentas sin caracteres corruptos y cálculos de amortizaciones según tablas AEAT.
"""

import sqlite3
import pytest
from app.infrastructure.database.pgc_seeder import PgcSeeder
from app.domain.services.depreciation_engine import DepreciationEngine


def test_pgc_seeder_contains_required_accounts_and_no_mojibake():
    """Valida que PgcSeeder inserte cuentas 681, 281, 217 y no contenga mojibake."""
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE pgc_accounts (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL
        )
    """)
    
    PgcSeeder.seed_accounts(conn)
    
    cursor = conn.cursor()
    cursor.execute("SELECT code, name, type FROM pgc_accounts")
    accounts = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
    
    # Comprobar cuentas críticas para amortizaciones y fiscalidad
    assert "68100000" in accounts, "La cuenta 68100000 debe existir en el cuadro de cuentas"
    assert "28100000" in accounts, "La cuenta 28100000 debe existir en el cuadro de cuentas"
    assert "21700000" in accounts, "La cuenta 21700000 debe existir en el cuadro de cuentas"
    assert "43000000" in accounts
    assert "57200000" in accounts
    
    # Comprobar ausencia de caracteres corruptos (mojibake)
    for code, (name, _) in accounts.items():
        assert "\ufffd" not in name, f"Mojibake detectado en cuenta {code}: {name}"
        assert "Ã" not in name, f"Mojibake detectado en cuenta {code}: {name}"
        
    assert "Amortización" in accounts["68100000"][0]
    conn.close()


def test_depreciation_engine_linear_calculation():
    """Valida el cálculo de amortización lineal anual y prorrateada de activos fijos."""
    engine = DepreciationEngine()
    
    # Activo adquirido el 01-01-2026 por 2.000€ al 25% anual (año completo)
    dep_full = engine.calculate_annual_depreciation(
        acquisition_value=2000.0,
        depreciation_rate=25.0,
        acquisition_date="2026-01-01",
        fiscal_year=2026
    )
    assert dep_full["annual_amount"] == 500.0
    assert dep_full["accumulated_depreciation"] == 500.0
    assert dep_full["net_book_value"] == 1500.0
    
    # Activo adquirido a mitad de año (01-07-2026) -> 6 meses de amortización en 2026
    dep_half = engine.calculate_annual_depreciation(
        acquisition_value=2000.0,
        depreciation_rate=25.0,
        acquisition_date="2026-07-01",
        fiscal_year=2026
    )
    assert dep_half["annual_amount"] == 250.0  # 500.0 * (6/12)
    assert dep_half["net_book_value"] == 1750.0


def test_depreciation_engine_stops_at_net_book_value_zero():
    """Valida que un activo no se amortice por encima de su valor de adquisición."""
    engine = DepreciationEngine()
    
    # Activo con valor 1.000€ y amortización acumulada previa de 900€
    dep_capped = engine.calculate_annual_depreciation(
        acquisition_value=1000.0,
        depreciation_rate=20.0,  # 200€ al año
        acquisition_date="2022-01-01",
        fiscal_year=2026,
        previous_accumulated=900.0
    )
    # Solo debe amortizar 100€ restantes
    assert dep_capped["annual_amount"] == 100.0
    assert dep_capped["accumulated_depreciation"] == 1000.0
    assert dep_capped["net_book_value"] == 0.0
