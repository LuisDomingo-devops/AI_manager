"""
Pruebas unitarias de concordancia matemática trimestral y auditoría interna para el Modelo 347.
Verifica que 1T + 2T + 3T + 4T == Total Anual con tolerancia de 0.05 € y reporte de discrepancias.
"""

import pytest
from app.domain.models.billing import (
    Model347DeclaredDTO,
    Model347ResultDTO,
    Model347ReconciliationDTO
)
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService


def test_modelo_347_reconciliation_perfect_match():
    """
    Verifica que una declaración donde todos los declarados cuadran exactamente
    entre sus 4 trimestres y el total anual sea declarada como matemáticamente cuadrada.
    """
    records = [
        Model347DeclaredDTO(
            nif="B12345674",
            name="EMPRESA 1 SL",
            province_code="28",
            operation_key="A",
            total_annual_amount=10000.00,
            quarter_1_amount=2500.00,
            quarter_2_amount=2500.00,
            quarter_3_amount=2500.00,
            quarter_4_amount=2500.00
        ),
        Model347DeclaredDTO(
            nif="A98765432",
            name="EMPRESA 2 SA",
            province_code="08",
            operation_key="B",
            total_annual_amount=20000.00,
            quarter_1_amount=5000.00,
            quarter_2_amount=5000.00,
            quarter_3_amount=5000.00,
            quarter_4_amount=5000.00
        )
    ]
    result = Model347ResultDTO(
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="DECLARANTE SL",
        total_declared_records=2,
        total_operations_amount=30000.00,
        declared_records=records
    )

    reconciliation = AnnualTaxAggregatorService.audit_and_reconcile_model_347(
        fiscal_year=2026,
        model_347_result=result
    )

    assert reconciliation.is_mathematically_reconciled is True
    assert reconciliation.quarterly_difference == 0.0
    assert reconciliation.has_rounding_tolerance is False
    assert len(reconciliation.discrepancies) == 0


def test_modelo_347_reconciliation_with_cent_rounding_tolerance():
    """
    Verifica que desviaciones por redondeo de céntimos en facturas individuales
    (diferencia <= 0.05 €) sean aceptadas activando la marca has_rounding_tolerance.
    """
    records = [
        Model347DeclaredDTO(
            nif="B12345674",
            name="EMPRESA REDONDEO SL",
            province_code="28",
            operation_key="A",
            total_annual_amount=10000.03,
            quarter_1_amount=2500.01,
            quarter_2_amount=2500.01,
            quarter_3_amount=2500.01,
            quarter_4_amount=2500.01  # Suma = 10000.04 -> diff = 0.01
        )
    ]
    result = Model347ResultDTO(
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="DECLARANTE SL",
        total_declared_records=1,
        total_operations_amount=10000.03,
        declared_records=records
    )

    reconciliation = AnnualTaxAggregatorService.audit_and_reconcile_model_347(
        fiscal_year=2026,
        model_347_result=result
    )

    assert reconciliation.is_mathematically_reconciled is True
    assert reconciliation.quarterly_difference == pytest.approx(0.01, abs=1e-3)
    assert reconciliation.has_rounding_tolerance is True


def test_modelo_347_declared_dto_rejects_exceeded_discrepancy():
    """
    Verifica que el modelo Pydantic Model347DeclaredDTO rechace de forma estricta
    cualquier discrepancia trimestral superior a 0.05 € al instanciarse.
    """
    with pytest.raises(ValueError, match="Discrepancia trimestral"):
        Model347DeclaredDTO(
            nif="B12345674",
            name="EMPRESA DESCUADRADA SL",
            province_code="28",
            operation_key="A",
            total_annual_amount=10000.00,
            quarter_1_amount=2500.00,
            quarter_2_amount=2500.00,
            quarter_3_amount=2500.00,
            quarter_4_amount=2000.00  # Suma = 9500 -> diff = 500 €
        )
