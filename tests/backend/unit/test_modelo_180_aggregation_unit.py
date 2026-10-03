"""
Tests unitarios para la agregación de facturas de arrendamiento y validación catastral (Modelo 180).
"""

import pytest
from pydantic import ValidationError
from app.domain.models.billing import (
    InmuebleArrendadoDTO,
    Model180PerceptorDTO,
    Model180ResultDTO
)
from app.domain.services.annual_tax_service import AnnualTaxAggregatorService


def test_inmueble_situacion_1_valida():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="ALCALA",
        numero="10",
        municipio="MADRID",
        codigo_postal="28014",
        codigo_provincia="28"
    )
    assert inmueble.situacion_inmueble == 1
    assert inmueble.referencia_catastral == "9872023VH5797S0001WX"


def test_inmueble_situacion_1_error_longitud_referencia():
    with pytest.raises(ValidationError):
        InmuebleArrendadoDTO(
            situacion_inmueble=1,
            referencia_catastral="12345",  # Menor a 20 chars
            nombre_via="ALCALA",
            municipio="MADRID",
            codigo_postal="28014"
        )


def test_inmueble_situacion_3_sin_referencia_valida():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=3,
        referencia_catastral=None,
        tipo_via="CL",
        nombre_via="PARAJE LA HUERTA",
        numero="SN",
        municipio="CHINCHON",
        codigo_postal="28370",
        codigo_provincia="28"
    )
    assert inmueble.situacion_inmueble == 3
    assert inmueble.referencia_catastral is None


def test_inmueble_situacion_3_error_si_tiene_referencia():
    with pytest.raises(ValidationError):
        InmuebleArrendadoDTO(
            situacion_inmueble=3,
            referencia_catastral="9872023VH5797S0001WX",
            nombre_via="CAMINO",
            municipio="PUEBLO",
            codigo_postal="28001"
        )


def test_inmueble_situacion_3_error_si_falta_domicilio():
    with pytest.raises(ValidationError):
        InmuebleArrendadoDTO(
            situacion_inmueble=3,
            referencia_catastral=None,
            nombre_via="",
            municipio="MADRID",
            codigo_postal="28014"
        )


def test_inmueble_situacion_4_extranjero():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=4,
        referencia_catastral=None,
        nombre_via="RUE DE LA PAIX",
        municipio="PARIS",
        codigo_postal="75001"
    )
    assert inmueble.situacion_inmueble == 4


def test_model_180_aggregation_from_data():
    inmueble1 = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="GRAN VIA",
        numero="1",
        municipio="MADRID",
        codigo_postal="28013",
        codigo_provincia="28"
    )

    perceptor1 = Model180PerceptorDTO(
        nif="12345678Z",
        name="ARRENDADOR UNO SA",
        province_code="28",
        base_retencion=12000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=2280.0,
        inmueble=inmueble1
    )

    result = AnnualTaxAggregatorService.calculate_model_180_from_perceptors(
        fiscal_year=2026,
        perceptors=[perceptor1]
    )

    assert result.fiscal_year == 2026
    assert result.total_perceptores == 1
    assert result.total_base_retenciones == 12000.0
    assert result.total_retenciones_practicadas == 2280.0
