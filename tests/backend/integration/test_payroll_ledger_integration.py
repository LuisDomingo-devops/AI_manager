"""
INTEGRATION TESTS — Integración Contable de Nóminas y Finiquitos en Libro Diario y Mayor.
"""

import pytest
from app.adapters.memory.memory import _get_connection, _init_db_schema
from app.domain.services.employee_service import EmployeeService
from app.domain.services.ledger_service import LedgerService
from app.tools.server.payroll_tools import (
    create_employee_tool,
    calculate_monthly_payroll_tool,
    issue_monthly_payroll_tool,
    calculate_settlement_tool,
    issue_settlement_and_dismissal_tool
)


@pytest.fixture(autouse=True)
def setup_test_db():
    with _get_connection() as conn:
        _init_db_schema(conn)
        EmployeeService.init_schema()
        try:
            conn.execute("DELETE FROM ledger_entries")
            conn.execute("DELETE FROM journal_entries")
        except Exception:
            pass
        conn.execute("DELETE FROM settlements")
        conn.execute("DELETE FROM payrolls")
        conn.execute("DELETE FROM tgss_afi_records")
        conn.execute("DELETE FROM employees")
        conn.commit()


@pytest.mark.asyncio
async def test_payroll_tools_guardrails_require_confirmation():
    # 1. Intentar dar de alta sin confirmación expresa
    res_alta = await create_employee_tool(
        nif="12345678Z",
        nss="281234567890",
        full_name="CARLOS SÁNCHEZ",
        gross_annual_salary=24000.0,
        start_date="2026-01-01",
        confirmed_by_user=False
    )
    assert res_alta["status"] == "pending_confirmation"

    # 2. Confirmar alta
    res_alta_ok = await create_employee_tool(
        nif="12345678Z",
        nss="281234567890",
        full_name="CARLOS SÁNCHEZ",
        gross_annual_salary=24000.0,
        start_date="2026-01-01",
        confirmed_by_user=True
    )
    assert res_alta_ok["status"] == "ok"
    emp_id = res_alta_ok["employee_id"]

    # 3. Intentar emitir nómina sin confirmación
    res_nom = await issue_monthly_payroll_tool(emp_id, month=4, year=2026, confirmed_by_user=False)
    assert res_nom["status"] == "pending_confirmation"


@pytest.mark.asyncio
async def test_issue_monthly_payroll_records_journal_entry():
    # Crear empleado
    emp_id = EmployeeService.create_employee({
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "CARLOS SÁNCHEZ GÓMEZ",
        "gross_annual_salary": 24000.0,
        "start_date": "2026-01-01",
        "irpf_rate": 10.0
    })

    # Emitir nómina de Abril 2026
    res = await issue_monthly_payroll_tool(emp_id, month=4, year=2026, confirmed_by_user=True)
    assert res["status"] == "ok"
    assert res["journal_entry_id"] > 0

    # Comprobar que el asiento contable en el Libro Diario existe y está 100% cuadrado
    diario = LedgerService.get_libro_diario(2026)
    assert len(diario) >= 1

    entry = diario[-1]
    total_debe = sum(a["debe"] for a in entry["apuntes"])
    total_haber = sum(a["haber"] for a in entry["apuntes"])
    assert round(total_debe, 2) == round(total_haber, 2)

    # Comprobar desglose de cuentas: 640 Sueldos (2000€), 642 SS Empresa (639.60€)
    debe_accounts = {a["account_code"]: a["debe"] for a in entry["apuntes"] if a["debe"] > 0}
    assert "64000000" in debe_accounts
    assert debe_accounts["64000000"] == 2000.00
    assert "64200000" in debe_accounts
    assert debe_accounts["64200000"] == 639.60


@pytest.mark.asyncio
async def test_issue_settlement_and_dismissal_records_journal_and_updates_status():
    emp_id = EmployeeService.create_employee({
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "ANA LÓPEZ",
        "gross_annual_salary": 24000.0,
        "start_date": "2025-01-01",
        "irpf_rate": 10.0
    })

    # Ejecutar despido objetivo a 30 de Junio de 2026
    res = await issue_settlement_and_dismissal_tool(
        employee_id=emp_id,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-06-30",
        vacation_days_taken=10.0,
        motive_desc="Reorganización productiva del área de desarrollo",
        confirmed_by_user=True
    )

    assert res["status"] == "ok"
    assert res["total_liquidado"] > 0
    assert res["finiquito_pdf"] is not None
    assert res["carta_despido_pdf"] is not None
    assert res["tgss_afi_baja"]["action"] == "MB"

    # Comprobar que el empleado cambió su estado a DISMISSED
    emp_updated = EmployeeService.get_employee(emp_id)
    assert emp_updated["status"] == "DISMISSED"
    assert emp_updated["end_date"] == "2026-06-30"

    # Comprobar asiento contable de liquidación (cuenta 641 de indemnización presente)
    diario = LedgerService.get_libro_diario(2026)
    last_entry = diario[-1]
    debe_accounts = {a["account_code"]: a["debe"] for a in last_entry["apuntes"] if a["debe"] > 0}
    assert "64100000" in debe_accounts # Indemnización
