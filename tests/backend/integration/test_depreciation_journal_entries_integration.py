"""
Test de Integración para Asientos de Amortización Automática (User Story 4).
Valida que se generen los asientos contables en cuentas 681 y 281 perfectamente cuadrados.
"""

import pytest
import sqlite3
from app.domain.services.depreciation_engine import DepreciationEngine
from app.domain.accounting.services import AccountingService
from app.infrastructure.database.pgc_seeder import PgcSeeder


def test_integration_depreciation_journal_entry():
    """Valida la generación de un asiento contable automático de amortización en partida doble."""
    dep_engine = DepreciationEngine()
    accounting = AccountingService()
    
    # Activo de prueba
    asset = {
        "code": "ACT-2026-001",
        "description": "Portátil Desarrollo IA",
        "acquisition_date": "2026-01-01",
        "acquisition_value": 1600.0,
        "depreciation_rate": 25.0,  # 400€ al año
        "previous_accumulated": 0.0
    }
    
    # Ejecutar contabilización de amortización
    journal_entry = dep_engine.post_depreciation_entry(
        tenant_id="default",
        asset=asset,
        fiscal_year=2026,
        accounting_service=accounting
    )
    
    assert journal_entry is not None
    assert journal_entry.is_balanced is True
    assert journal_entry.fiscal_year == 2026
    
    # Verificar movimientos en Libro Mayor para 68100000 y 28100000
    ledger_681 = accounting.get_ledger(tenant_id="default", account_code="68100000", fiscal_year=2026)
    ledger_281 = accounting.get_ledger(tenant_id="default", account_code="28100000", fiscal_year=2026)
    
    assert len(ledger_681) >= 1
    assert len(ledger_281) >= 1
    # 681 debe ir al Debe
    assert ledger_681[-1]["debit"] == 400.0
    assert ledger_681[-1]["credit"] == 0.0
    # 281 debe ir al Haber
    assert ledger_281[-1]["debit"] == 0.0
    assert ledger_281[-1]["credit"] == 400.0
