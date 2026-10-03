"""
Pruebas unitarias para la generación del fichero posicional telemático oficial BOE (.ses)
del Modelo 180 conforme a las Órdenes EHA/3895/2004 y HFP/1395/2021.
Cada registro debe tener exactamente 500 caracteres ASCII/UTF-8.
"""

import pytest
from app.domain.models.billing import (
    Model180ResultDTO,
    Model180PerceptorDTO,
    InmuebleArrendadoDTO,
    DeclarantInfoDTO
)
from app.domain.services.boe_export_service import BoeExportService
from app.domain.exceptions import BoeRecordFormattingError


@pytest.fixture
def sample_declarant():
    return DeclarantInfoDTO(
        nif="B12345678",
        name="EMPRESA ARRENDATARIA SL",
        phone="912345678",
        contact_person="JUAN PEREZ GARCIA"
    )


@pytest.fixture
def sample_model_180_result():
    inmueble_1 = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="GRAN VIA",
        numero="28",
        municipio="MADRID",
        codigo_postal="28013",
        codigo_provincia="28"
    )
    inmueble_2 = InmuebleArrendadoDTO(
        situacion_inmueble=3,
        referencia_catastral=None,
        tipo_via="AV",
        nombre_via="DIAGONAL",
        numero="100",
        municipio="BARCELONA",
        codigo_postal="08018",
        codigo_provincia="08"
    )

    perceptor_1 = Model180PerceptorDTO(
        nif="A11111111",
        name="INMOBILIARIA CENTRO SA",
        base_retencion=12000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=2280.0,
        inmueble=inmueble_1
    )
    perceptor_2 = Model180PerceptorDTO(
        nif="B22222222",
        name="PATRIMONIOS CATALUNYA SL",
        base_retencion=6000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=1140.0,
        inmueble=inmueble_2
    )

    return Model180ResultDTO(
        fiscal_year=2026,
        total_perceptores=2,
        total_base_retenciones=18000.0,
        total_retenciones_practicadas=3420.0,
        perceptores=[perceptor_1, perceptor_2]
    )


def test_registro_tipo_1_modelo_180_exact_500_chars(sample_declarant, sample_model_180_result):
    """Verifica que el Registro Tipo 1 (Declarante) tenga exactamente 500 caracteres y campos correctos."""
    service = BoeExportService()
    line1 = service._build_registro_tipo_1_180(sample_model_180_result, sample_declarant)

    assert len(line1) == 500
    assert line1[0] == "1"
    assert line1[1:4] == "180"
    assert line1[4:8] == "2026"
    assert line1[8:17] == "B12345678"
    assert line1[17:57] == "EMPRESA ARRENDATARIA SL".ljust(40)
    assert line1[57] == "T"
    assert line1[58:67] == "912345678"
    assert line1[67:107] == "JUAN PEREZ GARCIA".ljust(40)
    assert line1[107:120] == "1802026000001"
    assert line1[120] == " "
    assert line1[134:143] == "000000002"  # 2 perceptores
    # Base total 18000.00 € -> 15 chars: 13 enteros + 2 dec -> 000000001800000
    assert line1[143:158] == "000000001800000"
    # Retenciones 3420.00 € -> 000000000342000
    assert line1[158:173] == "000000000342000"
    assert line1[173:500] == " " * 327


def test_registro_tipo_2_modelo_180_exact_500_chars_situacion_1(sample_declarant, sample_model_180_result):
    """Verifica que el Registro Tipo 2 con situación 1 tenga 500 chars y referencia catastral completa."""
    service = BoeExportService()
    p1 = sample_model_180_result.perceptores[0]
    line2 = service._build_registro_tipo_2_180(p1, 2026, sample_declarant.nif)

    assert len(line2) == 500
    assert line2[0] == "2"
    assert line2[1:4] == "180"
    assert line2[4:8] == "2026"
    assert line2[8:17] == "B12345678"
    assert line2[17:26] == "A11111111"
    assert line2[26:66] == "INMOBILIARIA CENTRO SA".ljust(40)
    assert line2[66:68] == "28"  # Provincia Madrid
    # Base 12000.00 en 13 chars -> 0000001200000
    assert line2[81:94] == "0000001200000"
    # Porcentaje 19.00% en 13 chars -> 0000000001900
    assert line2[94:107] == "0000000001900"
    # Retencion 2280.00 en 13 chars -> 0000000228000
    assert line2[107:120] == "0000000228000"
    # Situación inmueble (pos 214 -> index 213)
    assert line2[213] == "1"
    # Ref catastral (pos 215-234 -> slice [214:234])
    assert line2[214:234] == "9872023VH5797S0001WX"
    # Tipo vía (pos 235-239 -> slice [234:239])
    assert line2[234:239] == "CL   "
    # Nombre vía (pos 240-289 -> slice [239:289])
    assert line2[239:289] == "GRAN VIA".ljust(50)
    # Número (pos 290-294 -> slice [289:294])
    assert line2[289:294] == "28   "
    # Municipio (pos 295-324 -> slice [294:324])
    assert line2[294:324] == "MADRID".ljust(30)
    # Código postal (pos 325-329 -> slice [324:329])
    assert line2[324:329] == "28013"
    # Reserva final (pos 330-500 -> slice [329:500])
    assert line2[329:500] == " " * 171


def test_registro_tipo_2_modelo_180_situacion_3_sin_catastro(sample_declarant, sample_model_180_result):
    """Verifica que el Registro Tipo 2 con situación 3 deje la referencia catastral en 20 espacios en blanco."""
    service = BoeExportService()
    p2 = sample_model_180_result.perceptores[1]
    line2 = service._build_registro_tipo_2_180(p2, 2026, sample_declarant.nif)

    assert len(line2) == 500
    assert line2[213] == "3"
    assert line2[214:234] == " " * 20  # Sin referencia catastral
    assert line2[234:239] == "AV   "
    assert line2[239:289] == "DIAGONAL".ljust(50)
    assert line2[324:329] == "08018"
