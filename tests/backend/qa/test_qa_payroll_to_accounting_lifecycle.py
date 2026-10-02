"""
QA TESTS — Ciclo de Vida Completo de Recursos Humanos, Nóminas, Ficheros TGSS (AFI/CRA) y Contabilidad PGC.
Valida:
1. Alta de empleado y generación de AFI MA (Acción de Alta).
2. Cálculo oficial de nómina, PDF Orden ESS/2098/2014 y asiento contable de nómina cuadrado (640/642/476/4751/465).
3. Generación y registro de remesa mensual XML CRA para SILTRA con tabla tgss_cra_records.
4. Despido objetivo, cálculo de finiquito con indemnización (cuenta 64100000), baja AFI MB (causa 51 + L13) y cuadre contable.
5. Ejecución integrada a través de las tools de servidor en app/tools/server/payroll_tools.py.
"""

import pytest
from decimal import Decimal
from pathlib import Path
from datetime import datetime

from app.adapters.memory.memory import _get_connection, _init_db_schema
from app.domain.services.employee_service import EmployeeService
from app.domain.services.payroll_engine import PayrollEngine
from app.domain.services.payroll_pdf_service import PayrollPdfService
from app.domain.services.tgss_affiliation_service import TgssAffiliationService
from app.domain.services.tgss_cra_service import TgssCraService
from app.domain.services.ledger_service import LedgerService
from app.tools.server.payroll_tools import (
    create_employee_tool,
    issue_monthly_payroll_tool,
    generate_cra_monthly_file_tool,
    issue_settlement_and_dismissal_tool
)


@pytest.fixture(autouse=True)
def setup_qa_database():
    with _get_connection() as conn:
        _init_db_schema(conn)
        # Aseguramos que la tabla tgss_cra_records esté disponible para los tests
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tgss_cra_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                period_month INTEGER NOT NULL,
                period_year INTEGER NOT NULL,
                ccc TEXT NOT NULL,
                total_workers INTEGER NOT NULL,
                total_amount REAL NOT NULL,
                xml_sha256 TEXT NOT NULL,
                generated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'GENERATED'
            )
        """)
        conn.commit()


@pytest.mark.asyncio
async def test_full_payroll_and_accounting_lifecycle_qa():
    # -------------------------------------------------------------
    # FASE 1: Alta de Empleado y Generación de AFI MA
    # -------------------------------------------------------------
    emp_payload = {
        "nif": "12345678Z",
        "nss": "281234567890",
        "full_name": "ROBERTO SÁNCHEZ GÓMEZ",
        "gross_annual_salary": 24000.0,
        "start_date": "2026-01-01",
        "contract_type": "100",
        "contribution_group": 1,
        "num_paychecks": 12
    }
    emp_id = EmployeeService.create_employee(emp_payload)
    assert emp_id > 0

    emp = EmployeeService.get_employee(emp_id)
    assert emp["full_name"] == "ROBERTO SÁNCHEZ GÓMEZ"
    assert emp["status"] == "ACTIVE"

    # Generación y validación AFI de Alta (MA)
    afi_alta = TgssAffiliationService.generate_alta_afi(emp, ccc="28123456789")
    assert afi_alta["action"] == "MA"
    alta_path = Path(afi_alta["file_path"])
    assert alta_path.exists()
    alta_content = alta_path.read_text(encoding="utf-8")
    assert "EMP*0111*28123456789" in alta_content
    assert "TRA*281234567890*12345678Z*MA*20260101" in alta_content

    # -------------------------------------------------------------
    # FASE 2: Cálculo de Nómina, PDF y Asiento Contable Cuadrado
    # -------------------------------------------------------------
    payroll = PayrollEngine.calculate_monthly_payroll(
        employee=emp,
        month=1,
        year=2026,
        family_situation=1,
        num_children=0
    )
    assert payroll["gross_total"] == 2000.0
    assert payroll["salary_base"] == 2000.0
    assert payroll["irpf_rate"] > 0
    assert payroll["net_salary"] > 0

    # Generación de PDF Oficial Orden ESS/2098/2014
    pdf_path = PayrollPdfService.generate_payroll_pdf(payroll, emp)
    assert Path(pdf_path).exists()
    assert pdf_path.endswith(".pdf")

    # Contabilización en Libro Diario oficial PGC
    payroll_entry_data = dict(payroll)
    payroll_entry_data["employee_name"] = emp["full_name"]
    payroll_entry_data["month"] = 1
    payroll_entry_data["year"] = 2026
    journal_id = LedgerService.record_payroll_asiento(payroll_entry_data, date_str="2026-01-28")
    assert journal_id > 0

    # Verificación de Asiento Contable (Partida Doble Estricta y Cuentas Oficiales)
    libro_diario = LedgerService.get_libro_diario(year=2026)
    asiento_nomina = next((entry for entry in libro_diario if entry["asiento_id"] == journal_id), None)
    assert asiento_nomina is not None, "El asiento de nómina no se encontró en el Libro Diario"

    apuntes = asiento_nomina["apuntes"]
    total_debe = Decimal("0.00")
    total_haber = Decimal("0.00")
    cuentas_presentes = set()

    for ap in apuntes:
        debe = Decimal(str(ap["debe"]))
        haber = Decimal(str(ap["haber"]))
        total_debe += debe
        total_haber += haber
        cuentas_presentes.add(ap["account_code"])

    # Comprobación de partida doble sin desviación
    assert total_debe == total_haber, f"Descuadre en asiento de nómina: Debe {total_debe} != Haber {total_haber}"
    # Verificación de cuentas PGC obligatorias
    assert "64000000" in cuentas_presentes
    assert "64200000" in cuentas_presentes
    assert "47600000" in cuentas_presentes
    assert "47510000" in cuentas_presentes
    assert "46500000" in cuentas_presentes

    # -------------------------------------------------------------
    # FASE 3: Remesa Mensual XML CRA para SILTRA
    # -------------------------------------------------------------
    # Guardamos nómina en tabla payrolls para que el servicio CRA la consolide
    with _get_connection() as conn:
        conn.execute("""
            INSERT INTO payrolls (
                payroll_code, employee_id, month, year, salary_base, extra_pay_prorata, gross_total,
                bccc, bccp, ss_worker_total, ss_employer_total, irpf_rate, irpf_amount, net_salary,
                pdf_path, journal_entry_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"NOM-{emp['id']}-2026-01", emp["id"], 1, 2026,
            payroll["salary_base"], payroll["extra_pay_prorata"], payroll["gross_total"],
            payroll["bccc"], payroll["bccp"], payroll["ss_worker_total"],
            payroll["ss_employer_total"], payroll["irpf_rate"], payroll["irpf_amount"],
            payroll["net_salary"], pdf_path, journal_id, "2026-01-28 10:00:00"
        ))
        conn.commit()

    cra_res = TgssCraService.generate_monthly_cra_xml(
        month=1,
        year=2026,
        ccc="28123456789"
    )
    assert cra_res["total_trabajadores"] == 1
    assert cra_res["total_importe"] == 2000.0
    cra_xml_path = Path(cra_res["file_path"])
    assert cra_xml_path.exists()
    cra_content = cra_xml_path.read_text(encoding="utf-8")
    assert "<MensajeCRA" in cra_content
    assert "<CodigoCuentaCotizacion>" in cra_content
    assert "<Regimen>0111</Regimen>" in cra_content
    assert "<Provincia>28</Provincia>" in cra_content
    assert "<Numero>1234567</Numero>" in cra_content
    assert "<DigitoControl>89</DigitoControl>" in cra_content
    assert "<NumeroAfiliacion>281234567890</NumeroAfiliacion>" in cra_content
    assert "<CodigoConcepto>0001</CodigoConcepto>" in cra_content
    assert "<Importe>2000.00</Importe>" in cra_content

    # Verificación en la tabla tgss_cra_records
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tgss_cra_records WHERE id = ?", (cra_res["record_id"],))
        rec = cursor.fetchone()
        assert rec is not None
        assert rec["month"] == 1
        assert rec["year"] == 2026
        assert rec["status"] == "GENERATED"

    # -------------------------------------------------------------
    # FASE 4: Despido Objetivo, Finiquito, Asiento 641 y Baja AFI MB
    # -------------------------------------------------------------
    settlement = PayrollEngine.calculate_settlement(
        employee=emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date_str="2026-06-30",
        vacation_days_taken=5.0
    )
    assert settlement["indemnity_amount"] > 0
    assert settlement["total_settlement"] > 0
    assert settlement["vacation_pending_days"] > 0

    settlement_entry_data = dict(settlement)
    settlement_entry_data["employee_name"] = emp["full_name"]
    settlement_entry_data["employee_id"] = emp["id"]
    settlement_entry_data["termination_date"] = "2026-06-30"

    settlement_journal_id = LedgerService.record_settlement_asiento(
        settlement_data=settlement_entry_data,
        date_str="2026-06-30"
    )
    assert settlement_journal_id > 0

    asiento_finiquito = next((entry for entry in LedgerService.get_libro_diario(year=2026) if entry["asiento_id"] == settlement_journal_id), None)
    assert asiento_finiquito is not None, "El asiento de finiquito no se encontró en el Libro Diario"

    finiquito_apuntes = asiento_finiquito["apuntes"]
    fin_debe = Decimal("0.00")
    fin_haber = Decimal("0.00")
    fin_cuentas = set()

    for ap in finiquito_apuntes:
        debe = Decimal(str(ap["debe"]))
        haber = Decimal(str(ap["haber"]))
        fin_debe += debe
        fin_haber += haber
        fin_cuentas.add(ap["account_code"])

    # Partida doble estricta en finiquito
    assert fin_debe == fin_haber, f"Descuadre en asiento de finiquito: Debe {fin_debe} != Haber {fin_haber}"
    # Verificación de cuenta 64100000 para indemnización según recomendación O2
    assert "64100000" in fin_cuentas
    assert "64000000" in fin_cuentas
    assert "46500000" in fin_cuentas

    # Fichero AFI de Baja con Causa 51 y L13
    afi_baja = TgssAffiliationService.generate_baja_afi(
        employee=emp,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-06-30",
        vacation_days_pending=settlement["vacation_pending_days"],
        ccc="28123456789"
    )
    assert afi_baja["action"] == "MB"
    assert afi_baja["cause_code"] == "51"
    baja_content = Path(afi_baja["file_path"]).read_text(encoding="utf-8")
    assert "MB*20260630*CAU*51*L13" in baja_content

    # Actualizar estado de empleado y verificar
    EmployeeService.update_employee_status(emp["id"], status="DISMISSED", end_date="2026-06-30")
    updated_emp = EmployeeService.get_employee(emp["id"])
    assert updated_emp["status"] == "DISMISSED"
    assert updated_emp["end_date"] == "2026-06-30"


@pytest.mark.asyncio
async def test_server_tools_payroll_and_cra_integration_qa():
    # Validación de tools completas con confirmación de usuario
    emp_res = await create_employee_tool(
        nif="87654321B",
        nss="289998887766",
        full_name="LAURA TORRES BLANCO",
        gross_annual_salary=36000.0,
        start_date="2026-01-01",
        confirmed_by_user=True
    )
    assert emp_res["status"] == "ok"
    emp_id = emp_res["employee_id"]

    # Emisión de nómina mediante tool
    nom_res = await issue_monthly_payroll_tool(
        employee_id=emp_id,
        month=2,
        year=2026,
        confirmed_by_user=True
    )
    assert nom_res["status"] == "ok"
    assert nom_res["journal_entry_id"] > 0
    assert Path(nom_res["pdf_path"]).exists()

    # Generación de CRA mediante tool
    cra_tool_res = await generate_cra_monthly_file_tool(
        month=2,
        year=2026,
        ccc="28123456789",
        confirmed_by_user=True
    )
    assert cra_tool_res["status"] == "ok"
    assert cra_tool_res["total_trabajadores"] >= 1
    assert Path(cra_tool_res["file_path"]).exists()

    # Despido y finiquito mediante tool
    settle_tool_res = await issue_settlement_and_dismissal_tool(
        employee_id=emp_id,
        termination_type="OBJECTIVE_DISMISSAL",
        termination_date="2026-02-28",
        vacation_days_taken=0.0,
        confirmed_by_user=True
    )
    assert settle_tool_res["status"] == "ok"
    assert settle_tool_res["journal_entry_id"] > 0
    assert Path(settle_tool_res["finiquito_pdf"]).exists()
    assert Path(settle_tool_res["tgss_afi_baja"]["file_path"]).exists()

    # Verificar que el empleado figura DISMISSED
    emp_after = EmployeeService.get_employee(emp_id)
    assert emp_after["status"] == "DISMISSED"
