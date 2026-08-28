"""
TESTS DE CONECTIVIDAD mTLS Y CUMPLIMIENTO CON LA SEGURIDAD SOCIAL (TGSS)
"""

from pathlib import Path
from app.adapters.memory.memory import _get_connection, _init_db_schema
from app.domain.services.employee_service import EmployeeService
from app.domain.services.tgss_affiliation_service import TgssAffiliationService


def test_tgss_afi_structure_compliance_full_lifecycle():
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

    # 1. Alta MA
    res_alta = TgssAffiliationService.generate_alta_afi(emp, ccc="28123456789")
    content_alta = Path(res_alta["file_path"]).read_text(encoding="utf-8")
    assert "EMP*0111*28123456789" in content_alta
    assert "*MA*20260401" in content_alta
    assert "*CON*100*GRP*01*1000" in content_alta

    # 2. Baja MB Despido Objetivo (51)
    res_baja_51 = TgssAffiliationService.generate_baja_afi(
        emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-06-30",
        vacation_days_pending=5.0,
        ccc="28123456789"
    )
    content_baja_51 = Path(res_baja_51["file_path"]).read_text(encoding="utf-8")
    assert "*MB*20260630*CAU*51*L13*5" in content_baja_51

    # 3. Baja MB Baja Voluntaria (53)
    res_baja_53 = TgssAffiliationService.generate_baja_afi(
        emp,
        termination_type="VOLUNTARY_RESIGNATION",
        termination_date="2026-07-15",
        vacation_days_pending=2.0,
        ccc="28123456789"
    )
    content_baja_53 = Path(res_baja_53["file_path"]).read_text(encoding="utf-8")
    assert "*MB*20260715*CAU*53*L13*2" in content_baja_53
