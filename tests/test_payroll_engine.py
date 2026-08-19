"""
UNIT TESTS — Motor de Nóminas, Finiquitos e Indemnizaciones de Alfonso.
"""

import pytest
from app.domain.services.employee_service import EmployeeService
from app.domain.services.payroll_engine import PayrollEngine
from app.adapters.memory.memory import _get_connection, _init_db_schema


@pytest.fixture(autouse=True)
def setup_test_db():
    with _get_connection() as conn:
        _init_db_schema(conn)
        EmployeeService.init_schema()
        conn.execute("DELETE FROM settlements")
        conn.execute("DELETE FROM payrolls")
        conn.execute("DELETE FROM tgss_afi_records")
        conn.execute("DELETE FROM employees")
        conn.commit()


def test_employee_crud_encrypted_storage():
    emp_data = {
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "CARLOS SÁNCHEZ GÓMEZ",
        "email": "carlos@example.com",
        "iban": "ES9121000418450200051332",
        "contract_type": "100",
        "contribution_group": 1,
        "start_date": "2024-01-01",
        "gross_annual_salary": 24000.0,
        "num_paychecks": 12,
        "irpf_rate": 12.0
    }
    emp_id = EmployeeService.create_employee(emp_data)
    assert emp_id > 0

    # Comprobar que en la base de datos está cifrado
    with _get_connection() as conn:
        row = conn.execute("SELECT nif_encrypted, full_name_encrypted, iban_encrypted FROM employees WHERE id = ?", (emp_id,)).fetchone()
        assert row["nif_encrypted"] != "12345678Z"
        assert row["full_name_encrypted"] != "CARLOS SÁNCHEZ GÓMEZ"
        assert row["iban_encrypted"] != "ES9121000418450200051332"

    # Comprobar que get_employee lo descifra con éxito
    emp = EmployeeService.get_employee(emp_id)
    assert emp["nif"] == "12345678Z"
    assert emp["full_name"] == "CARLOS SÁNCHEZ GÓMEZ"
    assert emp["monthly_base_salary"] == 2000.0
    assert emp["status"] == "ACTIVE"


def test_monthly_payroll_calculation_12_paychecks():
    emp = {
        "id": 1,
        "nif": "12345678Z",
        "full_name": "CARLOS SÁNCHEZ",
        "gross_annual_salary": 24000.0,
        "num_paychecks": 12,
        "contract_type": "100",
        "irpf_rate": 10.0
    }
    calc = PayrollEngine.calculate_monthly_payroll(emp, month=5, year=2026)

    assert calc["salary_base"] == 2000.0
    assert calc["gross_total"] == 2000.0
    assert calc["bccc"] == 2000.0
    assert calc["bccp"] == 2000.0

    # Descuentos Trabajador (4.70% CC + 1.55% Desempleo + 0.10% FP + 0.12% MEI = 6.47%)
    assert calc["ss_worker_cc"] == 94.00 # 2000 * 4.70%
    assert calc["ss_worker_unemployment"] == 31.00 # 2000 * 1.55%
    assert calc["ss_worker_fp"] == 2.00 # 2000 * 0.10%
    assert calc["ss_worker_mei"] == 2.40 # 2000 * 0.12%
    assert calc["ss_worker_total"] == 129.40 # 94 + 31 + 2 + 2.40

    # Retención IRPF (10%)
    assert calc["irpf_amount"] == 200.00 # 2000 * 10%

    # Líquido a percibir: 2000 - 129.40 - 200 = 1670.60 €
    assert calc["net_salary"] == 1670.60

    # Seguridad Social Empresa (23.60% + 5.50% + 0.20% + 0.60% + 0.58% + 1.50% = 31.98%)
    assert calc["ss_employer_cc"] == 472.00
    assert calc["ss_employer_unemployment"] == 110.00
    assert calc["ss_employer_fogasa"] == 4.00
    assert calc["ss_employer_fp"] == 12.00
    assert calc["ss_employer_mei"] == 11.60
    assert calc["ss_employer_atep"] == 30.00
    assert calc["ss_employer_total"] == 639.60

    # Coste total empresa: 2000 + 639.60 = 2639.60 €
    assert calc["total_cost_company"] == 2639.60


def test_settlement_voluntary_resignation_zero_indemnity():
    emp = {
        "id": 1,
        "nif": "12345678Z",
        "full_name": "CARLOS SÁNCHEZ",
        "start_date": "2024-01-01",
        "gross_annual_salary": 24000.0,
        "num_paychecks": 12,
        "vacation_days_per_year": 30
    }
    # Baja voluntaria a 15 de Junio de 2026 habiendo disfrutado 5 días de vacaciones
    settlement = PayrollEngine.calculate_settlement(
        emp,
        termination_type="VOLUNTARY_RESIGNATION",
        termination_date_str="2026-06-15",
        vacation_days_taken=5.0
    )

    # 1. Salario días trabajados del mes (15 días de 2.000€ mensual = 1.000€)
    assert settlement["worked_days_month"] == 15
    assert settlement["worked_days_amount"] == 1000.0

    # 2. Indemnización en baja voluntaria: 0,00 €
    assert settlement["indemnity_days_total"] == 0.0
    assert settlement["indemnity_amount"] == 0.0

    # 3. Vacaciones pendientes
    assert settlement["vacation_pending_days"] > 0
    assert settlement["vacation_pending_amount"] > 0
    assert settlement["total_settlement"] == round(settlement["worked_days_amount"] + settlement["vacation_pending_amount"], 2)


def test_settlement_objective_dismissal_20_days_per_year():
    emp = {
        "id": 1,
        "nif": "12345678Z",
        "full_name": "ANA LÓPEZ",
        "start_date": "2023-01-01",
        "gross_annual_salary": 36500.0, # 100 €/día regulador
        "num_paychecks": 12,
        "vacation_days_per_year": 30
    }
    # Despido objetivo a 31 de Diciembre de 2024 (2 años exactos = 24 meses)
    settlement = PayrollEngine.calculate_settlement(
        emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date_str="2024-12-31",
        vacation_days_taken=30.0
    )

    # Antigüedad: 2 años = 40 días de indemnización
    assert settlement["seniority_months"] == 24
    assert settlement["indemnity_days_total"] == 40.0
    # Salario diario = 36500 / 365 = 100 €/día -> Indemnización = 40 * 100 = 4000 €
    assert settlement["indemnity_amount"] == 4000.00
    assert settlement["is_exempt_irpf"] is True


def test_settlement_objective_dismissal_max_12_months_cap():
    emp = {
        "id": 1,
        "nif": "12345678Z",
        "full_name": "PEDRO MARTÍNEZ",
        "start_date": "2000-01-01",
        "gross_annual_salary": 24000.0, # 2.000 €/mes
        "num_paychecks": 12,
        "vacation_days_per_year": 30
    }
    # Despido objetivo tras 20 años de antigüedad
    # 20 años * 20 días = 400 días de salario (> 365 días / 12 mensualidades)
    settlement = PayrollEngine.calculate_settlement(
        emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date_str="2020-01-01",
        vacation_days_taken=0.0
    )

    # El tope legal del art. 53.1.b ET es de 12 mensualidades (24.000 €)
    max_cap = 2000.0 * 12.0 # 24.000 €
    assert settlement["indemnity_amount"] == max_cap
