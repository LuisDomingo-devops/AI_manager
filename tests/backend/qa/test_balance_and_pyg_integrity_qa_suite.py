"""
Suite de QA para Integridad Contable: Balance de Situación y Cuenta de Pérdidas y Ganancias (User Story 4).
Valida que ninguna cuenta con movimientos quede excluida y que se cumpla la ecuación fundamental contable.
"""

from decimal import Decimal
from datetime import date
import pytest
from app.domain.accounting.services import AccountingService
from app.domain.accounting.ports import RecordJournalEntryCommand
from app.domain.services.accounting_reporting_service import AccountingReportingService


def test_qa_balance_sheet_and_pyg_integrity():
    """Valida la generación íntegra y cuadre de Balance de Situación y PyG."""
    accounting = AccountingService()
    reporting = AccountingReportingService()
    tenant_id = "default"
    fiscal_year = 2026
    
    # 1. Asiento de Inicio / Capital: Banco a Capital
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 1, 1),
        fiscal_year=fiscal_year,
        concept="Constitución / Aportación inicial",
        lines=[
            {"account_code": "57200000", "debit": 10000.0, "credit": 0.0},
            {"account_code": "10000000", "debit": 0.0, "credit": 10000.0}
        ]
    ))
    
    # 2. Venta de Servicios: Clientes a Ventas e IVA
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 2, 1),
        fiscal_year=fiscal_year,
        concept="Factura emitida F2026-0001",
        lines=[
            {"account_code": "43000000", "debit": 2420.0, "credit": 0.0},
            {"account_code": "70500000", "debit": 0.0, "credit": 2000.0},
            {"account_code": "47700021", "debit": 0.0, "credit": 420.0}
        ]
    ))
    
    # 3. Gasto Operativo y Amortización:
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 3, 1),
        fiscal_year=fiscal_year,
        concept="Gastos diversos",
        lines=[
            {"account_code": "62900000", "debit": 500.0, "credit": 0.0},
            {"account_code": "57200000", "debit": 0.0, "credit": 500.0}
        ]
    ))
    accounting.record_entry(RecordJournalEntryCommand(
        tenant_id=tenant_id,
        entry_date=date(2026, 12, 31),
        fiscal_year=fiscal_year,
        concept="Dotación amortización inmovilizado",
        lines=[
            {"account_code": "68100000", "debit": 300.0, "credit": 0.0},
            {"account_code": "28100000", "debit": 0.0, "credit": 300.0}
        ]
    ))
    
    # Generar PyG
    pyg = reporting.generate_profit_and_loss(tenant_id=tenant_id, fiscal_year=fiscal_year)
    assert pyg["total_ingresos"] == 2000.0
    assert pyg["total_gastos"] == 800.0  # 500 (629) + 300 (681)
    assert pyg["resultado_ejercicio"] == 1200.0  # 2000 - 800
    
    # Generar Balance de Situación
    balance = reporting.generate_balance_sheet(tenant_id=tenant_id, fiscal_year=fiscal_year)
    total_activo = balance["total_activo"]
    total_pasivo_pn = balance["total_pasivo_y_patrimonio_neto"]
    
    # Ecuación fundamental: Activo = Pasivo + Patrimonio Neto (incluyendo resultado del ejercicio)
    assert abs(total_activo - total_pasivo_pn) < 0.01, f"Descuadre en Balance: Activo={total_activo}, Pasivo+PN={total_pasivo_pn}"
