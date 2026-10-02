"""
IRPF RETENTION ENGINE — Motor de retenciones del IRPF conforme al RD 439/2007 (arts. 80 a 89 y Modelo 145).
Aplica el algoritmo oficial de retenciones sobre rendimientos del trabajo de la AEAT con precisión Decimal.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional
from app.domain.schemas import IrpfCalculationDTO, IrpfFamilySituation
from app.infrastructure.adapters.file_tax_rules_adapter import FileTaxRulesAdapter


class IrpfRetentionEngine:

    @classmethod
    def calculate_withholding(
        cls,
        annual_gross: Decimal,
        family_situation: IrpfFamilySituation = IrpfFamilySituation.SITUATION_3,
        num_descendants: int = 0,
        num_descendants_under_3: int = 0,
        disability_grade: int = 0,
        contract_code: str = "100",
        tax_rules_port=None
    ) -> IrpfCalculationDTO:
        """
        Calcula el tipo de retención y la cuota mensual oficial del IRPF para rendimientos del trabajo.
        """
        if tax_rules_port:
            rules = tax_rules_port.get_rules().get("payroll", {})
        else:
            rules = FileTaxRulesAdapter().get_rules().get("payroll", {})

        annual_gross = Decimal(str(annual_gross)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if annual_gross <= Decimal("0.00"):
            return IrpfCalculationDTO(
                annual_gross=Decimal("0.00"),
                deductible_ss_worker_annual=Decimal("0.00"),
                general_deductible_expenses=Decimal("0.00"),
                article_20_reduction=Decimal("0.00"),
                tax_base_irpf=Decimal("0.00"),
                personal_family_minimum=Decimal("0.00"),
                quota_tax_base=Decimal("0.00"),
                quota_minimum=Decimal("0.00"),
                prior_quota=Decimal("0.00"),
                is_exempt_art_81=True,
                final_irpf_rate=Decimal("0.00"),
                monthly_retention_amount=Decimal("0.00")
            )

        # 1. Comprobación del límite cuantitativo de exclusión del artículo 81 RIRPF
        is_exempt = cls._check_art_81_exemption(annual_gross, family_situation, num_descendants, rules)
        if is_exempt:
            return IrpfCalculationDTO(
                annual_gross=annual_gross,
                deductible_ss_worker_annual=Decimal("0.00"),
                general_deductible_expenses=Decimal("2000.00"),
                article_20_reduction=Decimal("0.00"),
                tax_base_irpf=Decimal("0.00"),
                personal_family_minimum=Decimal("5550.00"),
                quota_tax_base=Decimal("0.00"),
                quota_minimum=Decimal("0.00"),
                prior_quota=Decimal("0.00"),
                is_exempt_art_81=True,
                final_irpf_rate=Decimal("0.00"),
                monthly_retention_amount=Decimal("0.00")
            )

        # 2. Estimación de cotizaciones a la Seguridad Social deducibles del trabajador (art. 19.2.a LIRPF)
        # Tasas obreras: CC 4.70% + Desempleo (1.55% o 1.60%) + FP 0.10% + MEI 0.12%
        is_temp = str(contract_code).startswith("4")
        w_unempl_rate = Decimal(str(rules.get("worker_unemployment_temp", 1.60))) if is_temp else Decimal(str(rules.get("worker_unemployment_rate", 1.55)))
        worker_ss_rate = (
            Decimal(str(rules.get("worker_cc_rate", 4.70))) +
            w_unempl_rate +
            Decimal(str(rules.get("worker_fp_rate", 0.10))) +
            Decimal(str(rules.get("worker_mei_rate", 0.12)))
        )
        max_annual_base_cap = Decimal(str(rules.get("max_monthly_base_cap", 4720.50))) * Decimal("12.00")
        cotizable_annual = min(annual_gross, max_annual_base_cap)
        ss_worker_annual = (cotizable_annual * (worker_ss_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # 3. Otros gastos deducibles generales (art. 19.2.f LIRPF: 2.000 € anuales)
        general_expenses = Decimal("2000.00")

        # 4. Reducción por obtención de rendimientos del trabajo (art. 20 LIRPF)
        net_before_art20 = annual_gross - ss_worker_annual - general_expenses
        art20_reduction = cls._calculate_art_20_reduction(net_before_art20)

        # Base imponible para retenciones
        tax_base = max(Decimal("0.00"), annual_gross - ss_worker_annual - general_expenses - art20_reduction)

        # 5. Determinación del Mínimo Personal y Familiar (arts. 82-84 RIRPF)
        min_personal = cls._calculate_personal_and_family_minimum(
            family_situation=family_situation,
            num_descendants=num_descendants,
            num_descendants_under_3=num_descendants_under_3,
            disability_grade=disability_grade,
            rules=rules
        )

        # 6. Aplicación de la escala de gravamen (art. 85 RIRPF)
        brackets = rules.get("irpf_brackets", [
            {"limit": 12450.00, "rate": 19.00},
            {"limit": 20200.00, "rate": 24.00},
            {"limit": 35200.00, "rate": 30.00},
            {"limit": 60000.00, "rate": 37.00},
            {"limit": 300000.00, "rate": 45.00},
            {"limit": None, "rate": 47.00}
        ])

        quota_base = cls._apply_scale(tax_base, brackets)
        quota_min = cls._apply_scale(min_personal, brackets)
        prior_quota = max(Decimal("0.00"), quota_base - quota_min)

        # 7. Tipo previo y cuota mensual
        raw_rate = (prior_quota / annual_gross) * Decimal("100.00")
        final_rate = max(Decimal("0.00"), min(Decimal("47.00"), raw_rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))
        
        monthly_gross = (annual_gross / Decimal("12.00")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        monthly_retention = (monthly_gross * (final_rate / Decimal("100.00"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return IrpfCalculationDTO(
            annual_gross=annual_gross,
            deductible_ss_worker_annual=ss_worker_annual,
            general_deductible_expenses=general_expenses,
            article_20_reduction=art20_reduction,
            tax_base_irpf=tax_base,
            personal_family_minimum=min_personal,
            quota_tax_base=quota_base,
            quota_minimum=quota_min,
            prior_quota=prior_quota,
            is_exempt_art_81=False,
            final_irpf_rate=final_rate,
            monthly_retention_amount=monthly_retention
        )

    @classmethod
    def _check_art_81_exemption(cls, annual_gross: Decimal, situation: IrpfFamilySituation, num_descendants: int, rules: Dict[str, Any]) -> bool:
        """Determina si la retribución no alcanza los umbrales del art. 81 RIRPF."""
        limits = rules.get("art_81_limits", {
            "situation_1": { "0": 15876.00, "1": 17260.00, "2_plus": 18640.00 },
            "situation_2": { "0": 17107.00, "1": 18130.00, "2_plus": 19260.00 },
            "situation_3": { "0": 15876.00, "1": 16340.00, "2_plus": 16860.00 }
        })
        sit_key = f"situation_{int(situation)}"
        sit_limits = limits.get(sit_key, limits.get("situation_3", {}))
        
        if num_descendants == 0:
            threshold = Decimal(str(sit_limits.get("0", 15876.00)))
        elif num_descendants == 1:
            threshold = Decimal(str(sit_limits.get("1", 16340.00)))
        else:
            threshold = Decimal(str(sit_limits.get("2_plus", 16860.00)))

        return annual_gross <= threshold

    @classmethod
    def _calculate_art_20_reduction(cls, net_salary_before: Decimal) -> Decimal:
        """Calcula la reducción por obtención de rendimientos del trabajo del artículo 20 LIRPF."""
        if net_salary_before <= Decimal("14047.50"):
            return Decimal("6498.00")
        elif net_salary_before <= Decimal("19747.50"):
            excess = net_salary_before - Decimal("14047.50")
            red = Decimal("6498.00") - (Decimal("1.14") * excess)
            return max(Decimal("0.00"), red.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
        return Decimal("0.00")

    @classmethod
    def _calculate_personal_and_family_minimum(
        cls,
        family_situation: IrpfFamilySituation,
        num_descendants: int,
        num_descendants_under_3: int,
        disability_grade: int,
        rules: Dict[str, Any]
    ) -> Decimal:
        """Calcula el importe del Mínimo Personal y Familiar según el Modelo 145."""
        mins = rules.get("irpf_minimums", {})
        total_min = Decimal(str(mins.get("taxpayer_general", 5550.00)))

        # Descendientes computables
        if num_descendants >= 1:
            total_min += Decimal(str(mins.get("descendant_1", 2400.00)))
        if num_descendants >= 2:
            total_min += Decimal(str(mins.get("descendant_2", 2700.00)))
        if num_descendants >= 3:
            total_min += Decimal(str(mins.get("descendant_3", 4000.00)))
        if num_descendants >= 4:
            extra = num_descendants - 3
            total_min += Decimal(str(mins.get("descendant_4_plus", 4500.00))) * Decimal(str(extra))

        if num_descendants_under_3 > 0:
            total_min += Decimal(str(mins.get("descendant_under_3_bonus", 2800.00))) * Decimal(str(num_descendants_under_3))

        # Discapacidad del contribuyente
        if disability_grade >= 65:
            total_min += Decimal("9000.00")
        elif disability_grade >= 33:
            total_min += Decimal("3000.00")

        return total_min.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def _apply_scale(cls, amount: Decimal, brackets: List[Dict[str, Any]]) -> Decimal:
        """Aplica los tramos progresivos de la escala del IRPF (artículo 85 RIRPF)."""
        if amount <= Decimal("0.00"):
            return Decimal("0.00")

        tax = Decimal("0.00")
        prev_limit = Decimal("0.00")

        for b in brackets:
            rate = Decimal(str(b["rate"])) / Decimal("100.00")
            limit = Decimal(str(b["limit"])) if b.get("limit") is not None else None

            if limit is not None:
                if amount > limit:
                    taxable_slice = limit - prev_limit
                    tax += taxable_slice * rate
                    prev_limit = limit
                else:
                    taxable_slice = amount - prev_limit
                    tax += taxable_slice * rate
                    break
            else:
                # Último tramo sin límite superior
                taxable_slice = amount - prev_limit
                tax += taxable_slice * rate
                break

        return tax.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
