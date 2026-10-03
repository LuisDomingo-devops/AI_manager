"""
Pruebas unitarias de agregación, filtrado de umbral cuantitativo (> 3.005,06 €),
claves de operación A y B, y detección de cobros en metálico (> 6.000,00 €) para el Modelo 347.
Conforme a RD 1065/2007 (Arts. 31 a 35).
"""

import pytest
from app.domain.models.billing import Model347DeclaredDTO, Model347ResultDTO
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService


def test_modelo_347_threshold_exclusion():
    """
    Verifica que las operaciones con un tercero cuyo volumen total anual sea inferior
    o igual a 3.005,06 € queden automáticamente excluidas de la declaración.
    """
    # Caso 1: Importe justo en el límite legal de 3.005,06 € -> Excluido
    invoices = [
        {"nif": "B11111111", "name": "PROVEEDOR MENOR", "category": "gasto", "base": 2483.52, "iva": 521.54, "quarter": 1} # Total = 3005.06
    ]
    result = AnnualTaxAggregatorService.aggregate_invoices_for_model_347(
        invoices=invoices,
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES SL"
    )
    assert len(result.declared_records) == 0
    assert result.total_declared_records == 0
    assert result.total_operations_amount == 0.0

    # Caso 2: Importe supera por un céntimo (3.005,07 €) -> Incluido
    invoices_included = [
        {"nif": "B22222222", "name": "PROVEEDOR JUSTO", "category": "gasto", "base": 2483.53, "iva": 521.54, "quarter": 2} # Total = 3005.07
    ]
    result_included = AnnualTaxAggregatorService.aggregate_invoices_for_model_347(
        invoices=invoices_included,
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES SL"
    )
    assert len(result_included.declared_records) == 1
    assert result_included.declared_records[0].nif == "B22222222"
    assert result_included.declared_records[0].total_annual_amount == 3005.07
    assert result_included.declared_records[0].operation_key == "A"


def test_modelo_347_operation_keys_segregation():
    """
    Verifica que las adquisiciones de bienes y servicios se asignen a Clave 'A'
    y las entregas de bienes y prestaciones de servicios a Clave 'B', sin netear compras y ventas.
    """
    invoices = [
        # Compras a PROV_CLIENTE SL (> 3005.06)
        {"nif": "B33333333", "name": "PROV CLIENTE SL", "category": "gasto", "base": 4000.0, "iva": 840.0, "quarter": 1},
        # Ventas a PROV_CLIENTE SL (> 3005.06)
        {"nif": "B33333333", "name": "PROV CLIENTE SL", "category": "ingreso", "base": 10000.0, "iva": 2100.0, "quarter": 3}
    ]
    result = AnnualTaxAggregatorService.aggregate_invoices_for_model_347(
        invoices=invoices,
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES SL"
    )
    assert len(result.declared_records) == 2
    keys = {d.operation_key: d for d in result.declared_records}
    assert "A" in keys
    assert "B" in keys
    assert keys["A"].total_annual_amount == 4840.0
    assert keys["B"].total_annual_amount == 12100.0


def test_modelo_347_cash_amount_threshold():
    """
    Verifica que los cobros en metálico superiores a 6.000,00 € en el año se reflejen
    en el campo de cobros en metálico del cliente correspondiente, mientras que importes
    menores o iguales a 6.000 € se consignen con 0.00 €.
    """
    invoices = [
        # Venta cliente 1: 15.000 € con cobro en metálico de 7.500 € (> 6.000 €)
        {"nif": "11111111H", "name": "CLIENTE EFECTIVO ALTO", "category": "ingreso", "base": 12396.69, "iva": 2603.31, "quarter": 2, "cash_amount": 7500.0},
        # Venta cliente 2: 8.000 € con cobro en metálico de 5.000 € (<= 6.000 €)
        {"nif": "22222222J", "name": "CLIENTE EFECTIVO BAJO", "category": "ingreso", "base": 6611.57, "iva": 1388.43, "quarter": 3, "cash_amount": 5000.0}
    ]
    result = AnnualTaxAggregatorService.aggregate_invoices_for_model_347(
        invoices=invoices,
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES SL"
    )
    records_by_nif = {d.nif: d for d in result.declared_records}
    assert records_by_nif["11111111H"].cash_amount == 7500.0
    assert records_by_nif["22222222J"].cash_amount == 0.0
    assert result.total_cash_amount == 7500.0
