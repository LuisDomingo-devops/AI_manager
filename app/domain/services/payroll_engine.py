"""
PAYROLL ENGINE — Motor de cálculo laboral de nóminas, cotizaciones SS y finiquitos.
"""

from datetime import datetime, date
from typing import Dict, Any, Tuple
from app.domain.schemas import PayrollResultSchema, SettlementResultSchema


class PayrollEngine:

    # Tipos de cotización de la Seguridad Social vigentes (2026)
    WORKER_CC_RATE = 4.70          # Contingencias comunes trabajador
    WORKER_UNEMPLOYMENT_RATE = 1.55 # Desempleo contrato indefinido
    WORKER_UNEMPLOYMENT_TEMP = 1.60 # Desempleo contrato temporal
    WORKER_FP_RATE = 0.10          # Formación profesional trabajador
    WORKER_MEI_RATE = 0.12         # MEI trabajador (2026)

    EMPLOYER_CC_RATE = 23.60       # Contingencias comunes empresa
    EMPLOYER_UNEMPLOYMENT_RATE = 5.50 # Desempleo empresa indefinido
    EMPLOYER_UNEMPLOYMENT_TEMP = 6.70 # Desempleo empresa temporal
    EMPLOYER_FOGASA_RATE = 0.20    # FOGASA empresa
    EMPLOYER_FP_RATE = 0.60        # Formación profesional empresa
    EMPLOYER_MEI_RATE = 0.58       # MEI empresa (2026)
    EMPLOYER_ATEP_RATE = 1.50      # Tarifa de primas promedio accidentes de trabajo

    @classmethod
    def calculate_monthly_payroll(cls, employee: Dict[str, Any], month: int, year: int) -> Dict[str, Any]:
        """
        Calcula la nómina mensual completa con bases de cotización, descuentos del trabajador y coste patronal.
        """
        gross_annual = float(employee["gross_annual_salary"])
        num_paychecks = int(employee.get("num_paychecks", 12))
        is_temp = str(employee.get("contract_type", "100")).startswith("4")

        # Salario base y prorrata de pagas extras
        if num_paychecks == 12:
            salary_base = round(gross_annual / 12.0, 2)
            extra_pay_prorata = 0.0
            gross_total = salary_base
        else:
            salary_base = round(gross_annual / 14.0, 2)
            extra_pay_prorata = round((salary_base * 2.0) / 12.0, 2)
            gross_total = salary_base

        # Base de Cotización a Contingencias Comunes (BCCC) y Profesionales (BCCP)
        bccc = round(gross_annual / 12.0, 2)
        bccp = bccc

        # Cotizaciones Trabajador
        w_cc = round(bccc * (cls.WORKER_CC_RATE / 100.0), 2)
        w_unempl_rate = cls.WORKER_UNEMPLOYMENT_TEMP if is_temp else cls.WORKER_UNEMPLOYMENT_RATE
        w_unempl = round(bccp * (w_unempl_rate / 100.0), 2)
        w_fp = round(bccp * (cls.WORKER_FP_RATE / 100.0), 2)
        w_mei = round(bccc * (cls.WORKER_MEI_RATE / 100.0), 2)
        w_total_ss = round(w_cc + w_unempl + w_fp + w_mei, 2)

        # Cotizaciones Empresa
        e_cc = round(bccc * (cls.EMPLOYER_CC_RATE / 100.0), 2)
        e_unempl_rate = cls.EMPLOYER_UNEMPLOYMENT_TEMP if is_temp else cls.EMPLOYER_UNEMPLOYMENT_RATE
        e_unempl = round(bccp * (e_unempl_rate / 100.0), 2)
        e_fogasa = round(bccp * (cls.EMPLOYER_FOGASA_RATE / 100.0), 2)
        e_fp = round(bccp * (cls.EMPLOYER_FP_RATE / 100.0), 2)
        e_mei = round(bccc * (cls.EMPLOYER_MEI_RATE / 100.0), 2)
        e_atep = round(bccp * (cls.EMPLOYER_ATEP_RATE / 100.0), 2)
        e_total_ss = round(e_cc + e_unempl + e_fogasa + e_fp + e_mei + e_atep, 2)

        # Retención IRPF
        irpf_rate = float(employee.get("irpf_rate", 10.0))
        irpf_amount = round(gross_total * (irpf_rate / 100.0), 2)

        # Líquido a percibir y coste total para el autónomo
        net_salary = round(gross_total - w_total_ss - irpf_amount, 2)
        total_cost_company = round(gross_total + e_total_ss, 2)

        return {
            "employee_id": employee["id"],
            "employee_name": employee["full_name"],
            "employee_nif": employee["nif"],
            "month": month,
            "year": year,
            "salary_base": salary_base,
            "extra_pay_prorata": extra_pay_prorata,
            "gross_total": gross_total,
            "bccc": bccc,
            "bccp": bccp,
            "ss_worker_cc": w_cc,
            "ss_worker_unemployment": w_unempl,
            "ss_worker_fp": w_fp,
            "ss_worker_mei": w_mei,
            "ss_worker_total": w_total_ss,
            "ss_employer_cc": e_cc,
            "ss_employer_unemployment": e_unempl,
            "ss_employer_fogasa": e_fogasa,
            "ss_employer_fp": e_fp,
            "ss_employer_mei": e_mei,
            "ss_employer_atep": e_atep,
            "ss_employer_total": e_total_ss,
            "irpf_rate": irpf_rate,
            "irpf_amount": irpf_amount,
            "net_salary": net_salary,
            "total_cost_company": total_cost_company
        }

    @classmethod
    def calculate_settlement(
        cls,
        employee: Dict[str, Any],
        termination_type: str,
        termination_date_str: str,
        vacation_days_taken: float = 0.0
    ) -> Dict[str, Any]:
        """
        Calcula el finiquito oficial y la indemnización legal por extinción de contrato:
        - VOLUNTARY_RESIGNATION: Días trabajados + Pagas extras + Vacaciones no disfrutadas (Indemnización 0€).
        - OBJECTIVE_DISMISSAL: Días trabajados + Pagas extras + Vacaciones + 20 días/año (tope 12 mensualidades).
        - DISCIPLINARY_DISMISSAL: Días trabajados + Pagas extras + Vacaciones (Indemnización 0€).
        """
        term_type = termination_type.upper()
        if term_type not in ("VOLUNTARY_RESIGNATION", "OBJECTIVE_DISMISSAL", "DISCIPLINARY_DISMISSAL"):
            raise ValueError(f"Tipo de extinción no soportado: {termination_type}")

        start_dt = datetime.strptime(employee["start_date"][:10], "%Y-%m-%d").date()
        term_dt = datetime.strptime(termination_date_str[:10], "%Y-%m-%d").date()

        if term_dt < start_dt:
            raise ValueError("La fecha de baja no puede ser anterior a la fecha de inicio del contrato.")

        gross_annual = float(employee["gross_annual_salary"])
        monthly_salary = round(gross_annual / 12.0, 2)
        daily_salary = round(gross_annual / 365.0, 4)

        # 1. Salario de los días trabajados en el mes de salida (base 30 días)
        day_of_month = term_dt.day
        worked_days = min(30, day_of_month)
        worked_days_amount = round((monthly_salary / 30.0) * worked_days, 2)

        # 2. Pagas extras pendientes (si no están prorrateadas mensualmente)
        num_paychecks = int(employee.get("num_paychecks", 12))
        extra_pays_pending = 0.0
        if num_paychecks == 14:
            # Devengo semestral de pagas extras (Verano: 1 Ene - 30 Jun, Navidad: 1 Jul - 31 Dic)
            month = term_dt.month
            if month <= 6:
                months_acc = month - 1 + (day_of_month / 30.0)
            else:
                months_acc = (month - 6) - 1 + (day_of_month / 30.0)
            extra_pays_pending = round((monthly_salary / 6.0) * months_acc, 2)

        # 3. Vacaciones devengadas y no disfrutadas
        # Por ley corresponden 2,5 días naturales por mes trabajado en el año en curso
        start_year_date = date(term_dt.year, 1, 1)
        contract_start_this_year = max(start_dt, start_year_date)
        days_in_current_year = (term_dt - contract_start_this_year).days + 1
        vacation_acc_days = round((days_in_current_year / 365.0) * float(employee.get("vacation_days_per_year", 30)), 2)
        vacation_pending_days = max(0.0, round(vacation_acc_days - vacation_days_taken, 2))
        vacation_pending_amount = round(vacation_pending_days * (gross_annual / 360.0), 2)

        # 4. Cálculo de Antigüedad exacta para la Indemnización (Art. 53.1.b y 56 ET)
        # Los meses incompletos se computan como meses enteros por imperativo legal
        total_days = (term_dt - start_dt).days + 1
        seniority_years = round(total_days / 365.25, 2)
        
        # Cálculo de meses completos computables (redondeo al alza de fracción de mes)
        months_diff = (term_dt.year - start_dt.year) * 12 + (term_dt.month - start_dt.month)
        if term_dt.day >= start_dt.day:
            seniority_months = months_diff + 1
        else:
            seniority_months = months_diff if months_diff > 0 else 1

        indemnity_days_total = 0.0
        indemnity_amount = 0.0
        is_exempt_irpf = True

        if term_type == "OBJECTIVE_DISMISSAL":
            # 20 días por año de servicio (20/12 días por mes computable)
            indemnity_days_total = round((seniority_months * 20.0) / 12.0, 2)
            raw_indemnity = round(indemnity_days_total * daily_salary, 2)
            
            # Tope máximo legal: 12 mensualidades (Art. 53.1.b ET)
            max_legal_indemnity = round(monthly_salary * 12.0, 2)
            indemnity_amount = min(raw_indemnity, max_legal_indemnity)
            is_exempt_irpf = True # Exento de IRPF hasta el límite del Art. 7.e LIRPF

        elif term_type in ("VOLUNTARY_RESIGNATION", "DISCIPLINARY_DISMISSAL"):
            indemnity_days_total = 0.0
            indemnity_amount = 0.0
            is_exempt_irpf = True

        total_settlement = round(
            worked_days_amount + extra_pays_pending + vacation_pending_amount + indemnity_amount,
            2
        )

        return {
            "employee_id": employee["id"],
            "employee_name": employee["full_name"],
            "employee_nif": employee["nif"],
            "termination_type": term_type,
            "termination_date": termination_date_str,
            "worked_days_month": worked_days,
            "worked_days_amount": worked_days_amount,
            "extra_pays_pending": extra_pays_pending,
            "vacation_pending_days": vacation_pending_days,
            "vacation_pending_amount": vacation_pending_amount,
            "seniority_years": seniority_years,
            "seniority_months": seniority_months,
            "daily_regulatory_salary": round(daily_salary, 2),
            "indemnity_days_total": indemnity_days_total,
            "indemnity_amount": indemnity_amount,
            "total_settlement": total_settlement,
            "is_exempt_irpf": is_exempt_irpf
        }
