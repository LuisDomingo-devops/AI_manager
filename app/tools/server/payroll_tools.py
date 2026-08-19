"""
PAYROLL TOOLS — Herramientas del asistente Alfonso para gestión laboral, nóminas, finiquitos y TGSS.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from app.domain.services.employee_service import EmployeeService
from app.domain.services.payroll_engine import PayrollEngine
from app.domain.services.payroll_pdf_service import PayrollPdfService
from app.domain.services.tgss_affiliation_service import TgssAffiliationService
from app.domain.services.ledger_service import LedgerService
from app.adapters.memory.memory import _get_connection
from app.utils.logger import tool_logger


async def create_employee_tool(
    nif: str,
    nss: str,
    full_name: str,
    gross_annual_salary: float,
    start_date: str,
    email: Optional[str] = None,
    iban: Optional[str] = None,
    contract_type: str = "100",
    contribution_group: int = 1,
    irpf_rate: float = 10.0,
    num_paychecks: int = 12,
    confirmed_by_user: bool = False
) -> dict:
    """
    Crea y da de alta un nuevo empleado en la base de datos cifrada de Alfonso y genera el fichero AFI de Alta para la TGSS.
    Requiere confirmación expresa del usuario.
    """
    if not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": (
                f"Propuesta de alta de empleado:\n"
                f"- Nombre: {full_name}\n"
                f"- NIF: {nif} | NSS: {nss}\n"
                f"- Salario Bruto Anual: {gross_annual_salary:,.2f} € ({num_paychecks} pagas)\n"
                f"- Fecha inicio: {start_date} | Contrato: {contract_type}\n"
                f"- Retención IRPF: {irpf_rate}%\n\n"
                f"¿Deseas confirmar el alta y generar el fichero de afiliación para la Seguridad Social? (confirmed_by_user=True)"
            )
        }

    try:
        emp_data = {
            "nif": nif,
            "nss": nss,
            "full_name": full_name,
            "email": email,
            "iban": iban,
            "contract_type": contract_type,
            "contribution_group": contribution_group,
            "start_date": start_date,
            "gross_annual_salary": gross_annual_salary,
            "num_paychecks": num_paychecks,
            "irpf_rate": irpf_rate,
            "vacation_days_per_year": 30
        }
        emp_id = EmployeeService.create_employee(emp_data)
        emp = EmployeeService.get_employee(emp_id)

        # Generar Fichero de Alta TGSS (Acción MA)
        afi_res = TgssAffiliationService.generate_alta_afi(emp)

        return {
            "status": "ok",
            "success": True,
            "message": f"Empleado '{full_name}' dado de alta exitosamente (ID: {emp_id}). Fichero de Alta TGSS generado.",
            "employee_id": emp_id,
            "tgss_afi_alta": afi_res
        }
    except Exception as e:
        tool_logger.exception("Error al dar de alta al empleado")
        return {"status": "error", "message": str(e)}


async def list_employees_tool(status: Optional[str] = None) -> dict:
    """Lista todos los empleados registrados con sus datos contractuales."""
    try:
        employees = EmployeeService.list_employees(status=status)
        return {
            "status": "ok",
            "count": len(employees),
            "employees": employees
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def calculate_monthly_payroll_tool(employee_id: int, month: int, year: int) -> dict:
    """Calcula el borrador de nómina mensual de un empleado con todas las deducciones y cuotas patronales."""
    try:
        emp = EmployeeService.get_employee(employee_id)
        if not emp:
            return {"status": "error", "message": f"No se encontró el empleado con ID {employee_id}"}

        calc = PayrollEngine.calculate_monthly_payroll(emp, month=month, year=year)
        return {
            "status": "ok",
            "payroll_draft": calc
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def issue_monthly_payroll_tool(
    employee_id: int,
    month: int,
    year: int,
    confirmed_by_user: bool = False
) -> dict:
    """
    Emite en firme la nómina mensual de un empleado:
    1. Genera el PDF oficial del Recibo de Salarios (Orden ESS/2098/2014).
    2. Registra el asiento de partida doble en el Libro Diario (640, 642, 476, 4751, 572).
    3. Guarda el registro en la base de datos de nóminas.
    """
    emp = EmployeeService.get_employee(employee_id)
    if not emp:
        return {"status": "error", "message": f"No se encontró el empleado con ID {employee_id}"}

    payroll = PayrollEngine.calculate_monthly_payroll(emp, month=month, year=year)

    if not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": (
                f"Propuesta de emisión de nómina (Mes {month}/{year}) para {emp['full_name']}:\n"
                f"- Salario Bruto: {payroll['gross_total']:,.2f} €\n"
                f"- Retención IRPF ({payroll['irpf_rate']}%): -{payroll['irpf_amount']:,.2f} €\n"
                f"- Descuento Seguridad Social: -{payroll['ss_worker_total']:,.2f} €\n"
                f"- Líquido a Pagar en Cuenta: {payroll['net_salary']:,.2f} €\n"
                f"- Coste Total para la Empresa (Bruto + SS Patronal {payroll['ss_employer_total']:,.2f}€): {payroll['total_cost_company']:,.2f} €\n\n"
                f"¿Deseas confirmar la emisión, generar el PDF oficial y contabilizar el asiento en el Libro Diario? (confirmed_by_user=True)"
            ),
            "payroll_draft": payroll
        }

    try:
        # 1. Generar PDF Oficial
        pdf_path = PayrollPdfService.generate_payroll_pdf(payroll, emp)

        # 2. Asiento contable de nómina en Libro Diario
        # Debe: 64000000 (Sueldos Brutos) + 64200000 (SS Empresa)
        # Haber: 47511100 (IRPF Retenido) + 47600000 (SS Total Acreedora: Trabajador + Empresa) + 57200000 (Banco / Líquido)
        total_ss_deuda = round(payroll["ss_worker_total"] + payroll["ss_employer_total"], 2)
        date_str = f"{year}-{str(month).zfill(2)}-28"
        payroll_code = f"NOM-{emp['id']}-{year}-{str(month).zfill(2)}"

        apuntes = [
            {"account_code": "64000000", "debe": payroll["gross_total"], "haber": 0.0},
            {"account_code": "64200000", "debe": payroll["ss_employer_total"], "haber": 0.0},
            {"account_code": "47511100", "debe": 0.0, "haber": payroll["irpf_amount"]},
            {"account_code": "47600000", "debe": 0.0, "haber": total_ss_deuda},
            {"account_code": "57200000", "debe": 0.0, "haber": payroll["net_salary"]}
        ]

        journal_id = LedgerService._insert_journal_and_ledger(
            date_str=date_str,
            concept=f"Nómina {month}/{year} - {emp['full_name']}",
            apuntes=apuntes
        )

        # 3. Guardar en tabla payrolls
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO payrolls (
                    payroll_code, employee_id, month, year, salary_base, extra_pay_prorata, gross_total,
                    bccc, bccp, ss_worker_total, ss_employer_total, irpf_rate, irpf_amount, net_salary,
                    pdf_path, journal_entry_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                payroll_code, emp["id"], month, year, payroll["salary_base"], payroll["extra_pay_prorata"],
                payroll["gross_total"], payroll["bccc"], payroll["bccp"], payroll["ss_worker_total"],
                payroll["ss_employer_total"], payroll["irpf_rate"], payroll["irpf_amount"], payroll["net_salary"],
                pdf_path, journal_id, now_str
            ))
            conn.commit()

        return {
            "status": "ok",
            "success": True,
            "message": f"Nómina {month}/{year} de {emp['full_name']} emitida y contabilizada exitosamente.",
            "payroll_code": payroll_code,
            "pdf_path": pdf_path,
            "journal_entry_id": journal_id,
            "summary": {
                "bruto": payroll["gross_total"],
                "irpf": payroll["irpf_amount"],
                "neto_trabajador": payroll["net_salary"],
                "coste_empresa": payroll["total_cost_company"]
            }
        }
    except Exception as e:
        tool_logger.exception("Error al emitir nómina")
        return {"status": "error", "message": str(e)}


async def calculate_settlement_tool(
    employee_id: int,
    termination_type: str,
    termination_date: str,
    vacation_days_taken: float = 0.0
) -> dict:
    """Calcula el borrador de finiquito e indemnización legal por extinción de contrato."""
    try:
        emp = EmployeeService.get_employee(employee_id)
        if not emp:
            return {"status": "error", "message": f"No se encontró el empleado con ID {employee_id}"}

        calc = PayrollEngine.calculate_settlement(
            emp,
            termination_type=termination_type,
            termination_date_str=termination_date,
            vacation_days_taken=vacation_days_taken
        )
        return {
            "status": "ok",
            "settlement_draft": calc
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def issue_settlement_and_dismissal_tool(
    employee_id: int,
    termination_type: str,
    termination_date: str,
    vacation_days_taken: float = 0.0,
    motive_desc: str = "Causas económicas y organizativas (Art. 52.c ET)",
    confirmed_by_user: bool = False
) -> dict:
    """
    Extingue el contrato de un empleado:
    1. Calcula el finiquito e indemnización legal correspondiente.
    2. Genera los PDFs oficiales: Documento de Finiquito y Carta de Despido (si aplica).
    3. Genera el Fichero de Baja AFI (Acción MB) para la Seguridad Social.
    4. Contabiliza el asiento de liquidación e indemnizaciones (640, 641, 572).
    5. Actualiza el estado del empleado a DISMISSED o RESIGNED.
    """
    emp = EmployeeService.get_employee(employee_id)
    if not emp:
        return {"status": "error", "message": f"No se encontró el empleado con ID {employee_id}"}

    settlement = PayrollEngine.calculate_settlement(
        emp,
        termination_type=termination_type,
        termination_date_str=termination_date,
        vacation_days_taken=vacation_days_taken
    )

    if not confirmed_by_user:
        return {
            "status": "pending_confirmation",
            "message": (
                f"Propuesta de Extinción Contractual y Finiquito ({termination_type}) para {emp['full_name']}:\n"
                f"- Fecha de Efectos: {termination_date}\n"
                f"- Antigüedad computable: {settlement['seniority_years']} años ({settlement['seniority_months']} meses)\n"
                f"- Salarios días mes: {settlement['worked_days_amount']:,.2f} €\n"
                f"- Pagas extras devengadas: {settlement['extra_pays_pending']:,.2f} €\n"
                f"- Vacaciones no disfrutadas ({settlement['vacation_pending_days']} días): {settlement['vacation_pending_amount']:,.2f} €\n"
                f"- Indemnización Legal ({settlement['indemnity_days_total']} días - Exenta IRPF): {settlement['indemnity_amount']:,.2f} €\n"
                f"--------------------------------------------------\n"
                f"TOTAL FINIQUITO A ABONAR: {settlement['total_settlement']:,.2f} €\n\n"
                f"¿Deseas confirmar la extinción, generar los documentos oficiales (Finiquito + Carta de despido), "
                f"generar el fichero de Baja AFI para la Seguridad Social y contabilizar el asiento? (confirmed_by_user=True)"
            ),
            "settlement_draft": settlement
        }

    try:
        # 1. Generar PDFs oficiales
        finiquito_pdf = PayrollPdfService.generate_settlement_pdf(settlement, emp)
        carta_despido_pdf = None
        if termination_type.upper() == "OBJECTIVE_DISMISSAL":
            carta_despido_pdf = PayrollPdfService.generate_dismissal_letter_pdf(settlement, emp, motive=motive_desc)

        # 2. Generar Fichero AFI de Baja (Acción MB) para la Seguridad Social
        afi_baja = TgssAffiliationService.generate_baja_afi(
            emp,
            termination_type=termination_type,
            termination_date=termination_date,
            vacation_days_pending=settlement["vacation_pending_days"]
        )

        # 3. Asiento contable de Finiquito e Indemnización
        # Debe: 64000000 (Sueldos y Salarios por días trabajados + pagas + vacaciones)
        # Debe: 64100000 (Indemnizaciones por despido)
        # Haber: 57200000 (Bancos)
        haberes = round(settlement["worked_days_amount"] + settlement["extra_pays_pending"] + settlement["vacation_pending_amount"], 2)
        indemnizacion = settlement["indemnity_amount"]

        apuntes = []
        if haberes > 0:
            apuntes.append({"account_code": "64000000", "debe": haberes, "haber": 0.0})
        if indemnizacion > 0:
            apuntes.append({"account_code": "64100000", "debe": indemnizacion, "haber": 0.0})
        apuntes.append({"account_code": "57200000", "debe": 0.0, "haber": settlement["total_settlement"]})

        journal_id = LedgerService._insert_journal_and_ledger(
            date_str=termination_date,
            concept=f"Finiquito e Indemnización extinción {emp['full_name']}",
            apuntes=apuntes
        )

        # 4. Guardar en tabla settlements y actualizar status del empleado
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        settlement_code = f"FIN-{emp['id']}-{termination_date.replace('-', '')[:8]}"

        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO settlements (
                    settlement_code, employee_id, termination_type, termination_date,
                    worked_days_amount, extra_pays_pending, vacation_pending_days, vacation_pending_amount,
                    indemnity_days, indemnity_amount, total_settlement, pdf_path, journal_entry_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                settlement_code, emp["id"], termination_type.upper(), termination_date,
                settlement["worked_days_amount"], settlement["extra_pays_pending"],
                settlement["vacation_pending_days"], settlement["vacation_pending_amount"],
                settlement["indemnity_days_total"], settlement["indemnity_amount"],
                settlement["total_settlement"], finiquito_pdf, journal_id, now_str
            ))
            conn.commit()

        new_status = "DISMISSED" if "DISMISSAL" in termination_type.upper() else "RESIGNED"
        EmployeeService.update_employee_status(emp["id"], status=new_status, end_date=termination_date)

        return {
            "status": "ok",
            "success": True,
            "message": f"Extinción contractual de {emp['full_name']} completada con éxito.",
            "settlement_code": settlement_code,
            "finiquito_pdf": finiquito_pdf,
            "carta_despido_pdf": carta_despido_pdf,
            "tgss_afi_baja": afi_baja,
            "journal_entry_id": journal_id,
            "total_liquidado": settlement["total_settlement"]
        }
    except Exception as e:
        tool_logger.exception("Error al procesar el finiquito")
        return {"status": "error", "message": str(e)}
