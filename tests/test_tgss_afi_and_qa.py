"""
QA TESTS — Generación de Ficheros de Afiliación TGSS (AFI) y PDFs Oficiales de Nómina y Finiquito.
"""

from pathlib import Path
from app.adapters.memory.memory import _get_connection, _init_db_schema
from app.domain.services.employee_service import EmployeeService
from app.domain.services.payroll_engine import PayrollEngine
from app.domain.services.payroll_pdf_service import PayrollPdfService
from app.domain.services.tgss_affiliation_service import TgssAffiliationService


def test_tgss_alta_afi_generation_format():
    with _get_connection() as conn:
        _init_db_schema(conn)
        EmployeeService.init_schema()

    emp_id = EmployeeService.create_employee({
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "CARLOS SÁNCHEZ GÓMEZ",
        "gross_annual_salary": 24000.0,
        "start_date": "2026-04-01",
        "contract_type": "100",
        "contribution_group": 1
    })
    emp = EmployeeService.get_employee(emp_id)

    res = TgssAffiliationService.generate_alta_afi(emp, ccc="28123456789")
    assert res["action"] == "MA"
    assert Path(res["file_path"]).exists()

    content = Path(res["file_path"]).read_text(encoding="utf-8")
    assert "EMP*0111*28123456789" in content
    assert "TRA*281234567890*12345678Z*MA*20260401" in content
    assert "CON*100*GRP*01*1000" in content


def test_tgss_baja_afi_generation_with_cause_codes_and_l13():
    with _get_connection() as conn:
        _init_db_schema(conn)
        EmployeeService.init_schema()

    emp_id = EmployeeService.create_employee({
        "nif": "87654321A",
        "nss": "289876543210",
        "full_name": "MARÍA RODRÍGUEZ",
        "gross_annual_salary": 30000.0,
        "start_date": "2025-01-01"
    })
    emp = EmployeeService.get_employee(emp_id)

    # 1. Baja por Despido Objetivo (Causa 51) con 6 días de vacaciones pendientes
    res_baja_obj = TgssAffiliationService.generate_baja_afi(
        emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-06-30",
        vacation_days_pending=6.0,
        ccc="28123456789"
    )
    assert res_baja_obj["action"] == "MB"
    assert res_baja_obj["cause_code"] == "51"
    content_obj = Path(res_baja_obj["file_path"]).read_text(encoding="utf-8")
    assert "MB*20260630*CAU*51*L13*6" in content_obj

    # 2. Baja Voluntaria (Causa 53)
    res_baja_vol = TgssAffiliationService.generate_baja_afi(
        emp,
        termination_type="VOLUNTARY_RESIGNATION",
        termination_date="2026-07-15",
        vacation_days_pending=2.0,
        ccc="28123456789"
    )
    assert res_baja_vol["cause_code"] == "53"
    content_vol = Path(res_baja_vol["file_path"]).read_text(encoding="utf-8")
    assert "MB*20260715*CAU*53*L13*2" in content_vol


def test_generate_official_payroll_pdf_ess_2098_2014(tmp_path):
    emp = {
        "id": 99,
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "CARLOS SÁNCHEZ",
        "gross_annual_salary": 24000.0,
        "contract_type": "100",
        "irpf_rate": 10.0
    }
    payroll = PayrollEngine.calculate_monthly_payroll(emp, month=5, year=2026)

    pdf_file = tmp_path / "test_nomina.pdf"
    res_path = PayrollPdfService.generate_payroll_pdf(payroll, emp, output_path=str(pdf_file))

    assert Path(res_path).exists()
    assert Path(res_path).stat().st_size > 1000 # Contiene contenido PDF válido


def test_generate_official_settlement_and_dismissal_pdfs(tmp_path):
    emp = {
        "id": 99,
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "CARLOS SÁNCHEZ",
        "start_date": "2024-01-01",
        "gross_annual_salary": 24000.0
    }
    settlement = PayrollEngine.calculate_settlement(
        emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date_str="2026-06-30",
        vacation_days_taken=5.0
    )

    # 1. Finiquito PDF
    finiquito_pdf = tmp_path / "test_finiquito.pdf"
    PayrollPdfService.generate_settlement_pdf(settlement, emp, output_path=str(finiquito_pdf))
    assert Path(finiquito_pdf).exists()
    assert Path(finiquito_pdf).stat().st_size > 1000

    # 2. Carta de Despido PDF
    carta_pdf = tmp_path / "test_carta_despido.pdf"
    PayrollPdfService.generate_dismissal_letter_pdf(settlement, emp, output_path=str(carta_pdf))
    assert Path(carta_pdf).exists()
    assert Path(carta_pdf).stat().st_size > 1000
