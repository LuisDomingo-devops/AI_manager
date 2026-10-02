"""
UNIT TESTS — Motor Oficial de Retenciones IRPF (RD 439/2007) y Cotizaciones a la Seguridad Social (Orden ESS/2098/2014)
"""
from decimal import Decimal
import pytest
from app.domain.services.irpf_retention_engine import IrpfRetentionEngine
from app.domain.services.payroll_engine import PayrollEngine
from app.domain.schemas import EmployeeContractDTO, IrpfFamilySituation


def test_irpf_exemption_under_article_81_threshold():
    """Rentas bajas que no alcanzan el límite cuantitativo del art. 81 RIRPF tienen tipo 0.00%."""
    # Situación 3 sin hijos, salario 15.000 € (inferior al umbral del art. 81)
    result = IrpfRetentionEngine.calculate_withholding(
        annual_gross=Decimal("15000.00"),
        family_situation=IrpfFamilySituation.SITUATION_3,
        num_descendants=0,
        num_descendants_under_3=0,
        disability_grade=0,
        contract_code="100"
    )
    assert result.is_exempt_art_81 is True
    assert result.final_irpf_rate == Decimal("0.00")
    assert result.monthly_retention_amount == Decimal("0.00")


def test_irpf_calculation_standard_profile():
    """Empleado estándar con salario 24.000 €, soltero/sin hijos (situación 3)."""
    result = IrpfRetentionEngine.calculate_withholding(
        annual_gross=Decimal("24000.00"),
        family_situation=IrpfFamilySituation.SITUATION_3,
        num_descendants=0,
        num_descendants_under_3=0,
        disability_grade=0,
        contract_code="100"
    )
    assert result.is_exempt_art_81 is False
    assert result.final_irpf_rate > Decimal("5.00")
    assert result.final_irpf_rate < Decimal("20.00")
    # Verificación de que la retención mensual calculada coincide con tasa * bruto mensual
    expected_monthly = (Decimal("2000.00") * (result.final_irpf_rate / Decimal("100.00"))).quantize(Decimal("0.01"))
    assert result.monthly_retention_amount == expected_monthly


def test_irpf_family_minimum_reduces_retention_rate():
    """Los descendientes y menores de 3 años aumentan el mínimo personal y minoran la retención."""
    # Sin hijos
    res_no_children = IrpfRetentionEngine.calculate_withholding(
        annual_gross=Decimal("35000.00"),
        family_situation=IrpfFamilySituation.SITUATION_1,
        num_descendants=0,
        num_descendants_under_3=0,
        disability_grade=0,
        contract_code="100"
    )

    # Con 2 hijos (uno menor de 3 años)
    res_with_children = IrpfRetentionEngine.calculate_withholding(
        annual_gross=Decimal("35000.00"),
        family_situation=IrpfFamilySituation.SITUATION_1,
        num_descendants=2,
        num_descendants_under_3=1,
        disability_grade=0,
        contract_code="100"
    )

    assert res_with_children.personal_family_minimum > res_no_children.personal_family_minimum
    assert res_with_children.final_irpf_rate < res_no_children.final_irpf_rate


def test_monthly_payroll_calculation_with_topes_cotizacion_and_decimal():
    """Cálculo riguroso de nómina con bases topadas por grupo de cotización y precisión Decimal."""
    # Salario muy elevado (70.000 € anuales = 5.833,33 €/mes).
    # La base BCCC mensual debe quedar topada a la base máxima (4.720,50 €).
    employee_high = {
        "id": 10,
        "nif": "12345678Z",
        "full_name": "DIRECTOR GENERAL",
        "gross_annual_salary": Decimal("70000.00"),
        "num_paychecks": 12,
        "contribution_group": 1,
        "contract_code": "100",
        "irpf_situation": 3,
        "num_descendants": 0,
        "cnae_code": "6201"
    }

    payroll = PayrollEngine.calculate_monthly_payroll(employee_high, month=4, year=2026)

    # Base BCCC topada al máximo reglamentario
    assert Decimal(str(payroll["bccc"])) <= Decimal("4720.50")
    assert Decimal(str(payroll["bccp"])) <= Decimal("4720.50")

    # Comprobación de sumas exactas Decimal
    gross = Decimal(str(payroll["gross_total"]))
    ss_worker = Decimal(str(payroll["ss_worker_total"]))
    irpf_amt = Decimal(str(payroll["irpf_amount"]))
    net = Decimal(str(payroll["net_salary"]))
    assert net == gross - ss_worker - irpf_amt

    ss_employer = Decimal(str(payroll["ss_employer_total"]))
    total_cost = Decimal(str(payroll["total_cost_company"]))
    assert total_cost == gross + ss_employer
