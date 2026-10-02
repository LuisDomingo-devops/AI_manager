from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from typing import Dict, Any, Tuple
from app.domain.schemas import PayrollResultSchema, SettlementResultSchema, IrpfFamilySituation
from app.domain.services.irpf_retention_engine import IrpfRetentionEngine


class PayrollEngine:

    @classmethod
    def calculate_monthly_payroll(cls, employee: Dict[str, Any], month: int, year: int, tax_rules_port=None, **kwargs) -> Dict[str, Any]:
        """
        Calcula la nómina mensual completa con bases de cotización con topes por grupo,
        descuentos del trabajador y coste patronal desglosado con precisión Decimal y algoritmo oficial IRPF.
        """
        emp_dict = dict(employee)
        emp_dict.update(kwargs)
        if "family_situation" in kwargs:
            emp_dict["irpf_situation"] = kwargs["family_situation"]
        if "num_children" in kwargs:
            emp_dict["num_descendants"] = kwargs["num_children"]
        employee = emp_dict
        if tax_rules_port:
            rules = tax_rules_port.get_rules().get("payroll", {})
        else:
            from app.infrastructure.adapters.file_tax_rules_adapter import FileTaxRulesAdapter
            rules = FileTaxRulesAdapter().get_rules().get("payroll", {})

        gross_annual = Decimal(str(employee["gross_annual_salary"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        num_paychecks = int(employee.get("num_paychecks", 12))
        contract_code = str(employee.get("contract_code", employee.get("contract_type", "100")))
        is_temp = contract_code.startswith("4")
        group = str(employee.get("contribution_group", 1))

        # Salario base y prorrata de pagas extras
        if num_paychecks == 12:
            salary_base = (gross_annual / Decimal("12.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            extra_pay_prorata = Decimal("0.00")
            gross_total = salary_base
        else:
            salary_base = (gross_annual / Decimal("14.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            extra_pay_prorata = ((salary_base * Decimal("2.00")) / Decimal("12.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            gross_total = salary_base

        # Base de Cotización a Contingencias Comunes (BCCC) y Profesionales (BCCP)
        raw_bccc = (gross_annual / Decimal("12.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        min_bases = rules.get("min_monthly_bases", {})
        min_base = Decimal(str(min_bases.get(group, 1323.00)))
        max_base = Decimal(str(rules.get("max_monthly_base_cap", 4720.50)))

        bccc = min(max_base, max(min_base, raw_bccc))
        bccp = bccc

        # Cotizaciones Trabajador
        w_cc_rate = Decimal(str(rules.get("worker_cc_rate", 4.70)))
        w_cc = (bccc * (w_cc_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        w_unempl_rate = Decimal(str(rules.get("worker_unemployment_temp", 1.60))) if is_temp else Decimal(str(rules.get("worker_unemployment_rate", 1.55)))
        w_unempl = (bccp * (w_unempl_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        w_fp_rate = Decimal(str(rules.get("worker_fp_rate", 0.10)))
        w_fp = (bccp * (w_fp_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        w_mei_rate = Decimal(str(rules.get("worker_mei_rate", 0.12)))
        w_mei = (bccc * (w_mei_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        w_total_ss = w_cc + w_unempl + w_fp + w_mei

        # Cotizaciones Empresa
        e_cc_rate = Decimal(str(rules.get("employer_cc_rate", 23.60)))
        e_cc = (bccc * (e_cc_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_unempl_rate = Decimal(str(rules.get("employer_unemployment_temp", 6.70))) if is_temp else Decimal(str(rules.get("employer_unemployment_rate", 5.50)))
        e_unempl = (bccp * (e_unempl_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_fogasa_rate = Decimal(str(rules.get("employer_fogasa_rate", 0.20)))
        e_fogasa = (bccp * (e_fogasa_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_fp_rate = Decimal(str(rules.get("employer_fp_rate", 0.60)))
        e_fp = (bccp * (e_fp_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_mei_rate = Decimal(str(rules.get("employer_mei_rate", 0.58)))
        e_mei = (bccc * (e_mei_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_atep_rate = Decimal(str(rules.get("employer_atep_rate", 1.50)))
        e_atep = (bccp * (e_atep_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        e_total_ss = e_cc + e_unempl + e_fogasa + e_fp + e_mei + e_atep

        # Retención IRPF Oficial
        if "irpf_situation" in employee or "use_official_irpf" in employee or "irpf_rate" not in employee:
            sit_val = int(employee.get("irpf_situation", 3))
            situation = IrpfFamilySituation(sit_val) if sit_val in (1, 2, 3) else IrpfFamilySituation.SITUATION_3
            irpf_dto = IrpfRetentionEngine.calculate_withholding(
                annual_gross=gross_annual,
                family_situation=situation,
                num_descendants=int(employee.get("num_descendants", 0)),
                num_descendants_under_3=int(employee.get("num_descendants_under_3", 0)),
                disability_grade=int(employee.get("disability_grade", 0)),
                contract_code=contract_code,
                tax_rules_port=tax_rules_port
            )
            irpf_rate = irpf_dto.final_irpf_rate
            irpf_amount = (gross_total * (irpf_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            irpf_rate = Decimal(str(employee["irpf_rate"])).quantize(Decimal("0.01"))
            irpf_amount = (gross_total * (irpf_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Líquido a percibir y coste total para el empleador
        net_salary = gross_total - w_total_ss - irpf_amount
        total_cost_company = gross_total + e_total_ss

        return {
            "employee_id": employee["id"],
            "employee_name": employee["full_name"],
            "employee_nif": employee["nif"],
            "month": month,
            "year": year,
            "salary_base": float(salary_base),
            "extra_pay_prorata": float(extra_pay_prorata),
            "gross_total": float(gross_total),
            "bccc": float(bccc),
            "bccp": float(bccp),
            "ss_worker_cc": float(w_cc),
            "ss_worker_unemployment": float(w_unempl),
            "ss_worker_fp": float(w_fp),
            "ss_worker_mei": float(w_mei),
            "ss_worker_total": float(w_total_ss),
            "ss_employer_cc": float(e_cc),
            "ss_employer_unemployment": float(e_unempl),
            "ss_employer_fogasa": float(e_fogasa),
            "ss_employer_fp": float(e_fp),
            "ss_employer_mei": float(e_mei),
            "ss_employer_atep": float(e_atep),
            "ss_employer_total": float(e_total_ss),
            "irpf_rate": float(irpf_rate),
            "irpf_amount": float(irpf_amount),
            "net_salary": float(net_salary),
            "total_cost_company": float(total_cost_company)
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
