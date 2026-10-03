"""
Tests unitarios para la conciliación matemática entre Modelo 180 y Modelo 115.
"""

import pytest
from app.domain.models.billing import (
    Model180ResultDTO,
    Model180PerceptorDTO,
    InmuebleArrendadoDTO
)
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService


@pytest.fixture
def sample_model_180_result():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        nombre_via="GRAN VIA",
        municipio="MADRID",
        codigo_postal="28013"
    )
    perceptor = Model180PerceptorDTO(
        nif="B12345674",
        name="INMOBILIARIA CENTRO SL",
        province_code="28",
        base_retencion=40000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=7600.0,
        inmueble=inmueble
    )
    return Model180ResultDTO(
        fiscal_year=2026,
        total_perceptores=1,
        total_base_retenciones=40000.0,
        total_retenciones_practicadas=7600.0,
        perceptores=[perceptor]
    )


def test_reconcile_model_180_with_115_cuadre_exacto(sample_model_180_result):
    declaraciones_115 = [
        {"quarter": 1, "resultado_total": 1900.0},
        {"quarter": 2, "resultado_total": 1900.0},
        {"quarter": 3, "resultado_total": 1900.0},
        {"quarter": 4, "resultado_total": 1900.0}
    ]
    service = AnnualTaxAggregatorService()
    reconciliation = service.reconcile_with_model_115(
        fiscal_year=2026,
        model_180_result=sample_model_180_result,
        quarterly_115_declarations=declaraciones_115
    )

    assert reconciliation.is_cuadrado is True
    assert reconciliation.is_tolerancia_redondeo is False
    assert reconciliation.diferencia_total == 0.0
    assert reconciliation.total_retenciones_115_anual == 7600.0
    assert len(reconciliation.discrepancias_detectadas) == 0


def test_reconcile_model_180_with_115_tolerancia_redondeo(sample_model_180_result):
    declaraciones_115 = [
        {"quarter": 1, "resultado_total": 1900.01},
        {"quarter": 2, "resultado_total": 1900.01},
        {"quarter": 3, "resultado_total": 1900.0},
        {"quarter": 4, "resultado_total": 1900.0}
    ]
    service = AnnualTaxAggregatorService()
    reconciliation = service.reconcile_with_model_115(
        fiscal_year=2026,
        model_180_result=sample_model_180_result,
        quarterly_115_declarations=declaraciones_115
    )

    assert reconciliation.is_cuadrado is True
    assert reconciliation.is_tolerancia_redondeo is True
    assert reconciliation.diferencia_total == 0.02
    assert len(reconciliation.discrepancias_detectadas) == 0


def test_reconcile_model_180_with_115_descuadre_bloqueante(sample_model_180_result):
    declaraciones_115 = [
        {"quarter": 1, "resultado_total": 1500.0},
        {"quarter": 2, "resultado_total": 1900.0},
        {"quarter": 3, "resultado_total": 1900.0},
        {"quarter": 4, "resultado_total": 1900.0}
    ]
    service = AnnualTaxAggregatorService()
    reconciliation = service.reconcile_with_model_115(
        fiscal_year=2026,
        model_180_result=sample_model_180_result,
        quarterly_115_declarations=declaraciones_115
    )

    assert reconciliation.is_cuadrado is False
    assert reconciliation.diferencia_total == 400.0
    assert len(reconciliation.discrepancias_detectadas) > 0
    assert "Descuadre estructural" in reconciliation.discrepancias_detectadas[0]
