"""
Pruebas unitarias posicionales byte a byte para la exportación telemática del Modelo 190 (Orden EHA/3127/2009).
"""

import hashlib
import pytest
from app.domain.models.billing import (
    Model190ResultDTO,
    Model190PerceptorDTO,
    DeclarantInfoDTO,
    BoeExportResultDTO
)
from app.domain.services.boe_export_service import BoeExportService


@pytest.fixture
def mock_model_190():
    perceptor_a = Model190PerceptorDTO(
        nif="12345678Z",
        name="GARCIA PEREZ, JUAN",
        province_code="28",
        clave="A",
        subclave="  ",
        percepciones_dinerarias=30000.0,
        retenciones_practicadas=4500.0,
        percepciones_especie_valoracion=600.0,
        percepciones_especie_ingresos_a_cuenta=90.0,
        percepciones_especie_repercutidos=90.0,
        ejercicio_devengo=0,
        discapacidad=0,
        tipo_contrato=1,
        reducciones_aplicables=0,
        ano_nacimiento=1985,
        situacion_familiar=3,
        conyuge_nif=None,
        conyuge_discapacidad=0,
        num_hijos=1,
        num_hijos_discapacidad=0,
        num_ascendientes=0
    )

    perceptor_g = Model190PerceptorDTO(
        nif="23456789A",
        name="LOPEZ SANCHEZ, MARIA",
        province_code="08",
        clave="G",
        subclave="01",
        percepciones_dinerarias=4000.0,
        retenciones_practicadas=600.0,
        percepciones_especie_valoracion=0.0,
        percepciones_especie_ingresos_a_cuenta=0.0,
        percepciones_especie_repercutidos=0.0,
        ejercicio_devengo=0,
        discapacidad=0,
        tipo_contrato=3,
        reducciones_aplicables=0,
        ano_nacimiento=0,
        situacion_familiar=0,
        conyuge_nif=None,
        conyuge_discapacidad=0,
        num_hijos=0,
        num_hijos_discapacidad=0,
        num_ascendientes=0
    )

    return Model190ResultDTO(
        fiscal_year=2026,
        declarant_nif="B12345678",
        total_perceptores=2,
        total_percepciones_dinerarias=34000.0,
        total_retenciones_practicadas=5100.0,
        total_percepciones_especie=600.0,
        total_ingresos_a_cuenta=90.0,
        total_ingresos_a_cuenta_repercutidos=90.0,
        total_percepciones_global=34600.0,
        perceptores=[perceptor_a, perceptor_g]
    )


@pytest.fixture
def mock_declarant():
    return DeclarantInfoDTO(
        nif="B12345678",
        name="TECH CONSULTING SERVICES SL",
        phone="912345678"
    )


def test_tipo_1_record_exact_500_chars(mock_model_190, mock_declarant):
    """Verifica que el Registro Tipo 1 mide exactamente 500 caracteres y cumple las posiciones BOE."""
    service = BoeExportService()
    line1 = service._build_registro_tipo_1_190(mock_model_190, mock_declarant)

    assert len(line1) == 500, f"El Registro Tipo 1 debe medir 500 caracteres, mide {len(line1)}"
    assert line1[0] == "1"
    assert line1[1:4] == "190"
    assert line1[4:8] == "2026"
    assert line1[8:17] == "B12345678"
    assert line1[17:57] == "TECH CONSULTING SERVICES SL".ljust(40)
    assert line1[57] == "T"
    assert line1[58:67] == "912345678"
    assert line1[67:107] == "TECH CONSULTING SERVICES SL".ljust(40)
    assert line1[107:120] == "1902026000001"  # Número identificativo 13 dígitos
    assert line1[120] == " "  # Ordinaria
    assert line1[121:134] == "0" * 13
    assert line1[134:143] == "000000002"  # 2 perceptores
    # Total percepciones global: 34600.00 euros -> 15 dígitos: "000000003460000"
    assert line1[143:158] == "000000003460000"
    # Total retenciones: 5100.00 euros -> 15 dígitos: "000000000510000"
    assert line1[158:173] == "000000000510000"
    # 327 espacios finales
    assert line1[173:500] == " " * 327


def test_tipo_2_record_exact_500_chars(mock_model_190, mock_declarant):
    """Verifica que cada Registro Tipo 2 mide exactamente 500 caracteres con claves A y G según el BOE."""
    service = BoeExportService()
    perceptor_a = mock_model_190.perceptores[0]
    line2_a = service._build_registro_tipo_2_190(perceptor_a, mock_model_190.fiscal_year, mock_declarant.nif)

    assert len(line2_a) == 500, f"El Registro Tipo 2 debe medir 500 caracteres, mide {len(line2_a)}"
    assert line2_a[0] == "2"
    assert line2_a[1:4] == "190"
    assert line2_a[4:8] == "2026"
    assert line2_a[8:17] == "B12345678"
    assert line2_a[17:26] == "12345678Z"
    assert line2_a[26:35] == " " * 9  # NIF representante
    assert line2_a[35:75] == "GARCIA PEREZ, JUAN".ljust(40)
    assert line2_a[75:77] == "28"
    assert line2_a[77] == "A"
    assert line2_a[78:80] == "  "
    # Dinerarias: 30000.00 -> 13 dígitos: "0000003000000"
    assert line2_a[80:93] == "0000003000000"
    # Retenciones: 4500.00 -> 13 dígitos: "0000000450000"
    assert line2_a[93:106] == "0000000450000"
    # Especie valor: 600.00 -> 13 dígitos: "0000000060000"
    assert line2_a[106:119] == "0000000060000"
    # Especie ingresos a cuenta: 90.00 -> "0000000009000"
    assert line2_a[119:132] == "0000000009000"
    # Especie repercutidos: 90.00 -> "0000000009000"
    assert line2_a[132:145] == "0000000009000"
    # Ejercicio devengo
    assert line2_a[145:149] == "0000"
    # Discapacidad
    assert line2_a[149] == "0"
    # Contrato
    assert line2_a[150] == "1"
    # Reducciones
    assert line2_a[151] == "0"
    # Año nacimiento
    assert line2_a[152:156] == "1985"
    # Situación familiar
    assert line2_a[156] == "3"
    # NIF cónyuge
    assert line2_a[157:166] == " " * 9
    # Discapacidad cónyuge
    assert line2_a[166] == "0"
    # Descendientes
    assert line2_a[167:169] == "01"
    # Descendientes discapacidad
    assert line2_a[169:171] == "00"
    # Ascendientes
    assert line2_a[171:173] == "00"
    # 327 espacios finales
    assert line2_a[173:500] == " " * 327

    # Verificar perceptor profesional Clave G
    perceptor_g = mock_model_190.perceptores[1]
    line2_g = service._build_registro_tipo_2_190(perceptor_g, mock_model_190.fiscal_year, mock_declarant.nif)
    assert len(line2_g) == 500
    assert line2_g[77] == "G"
    assert line2_g[78:80] == "01"
    assert line2_g[80:93] == "0000000400000"
    assert line2_g[93:106] == "0000000060000"


def test_export_model_190_boe_full_file(mock_model_190, mock_declarant):
    """Verifica la exportación completa a BOE del Modelo 190, CRLF, bytes y hash SHA-256."""
    service = BoeExportService()
    export_result = service.export_model_190_boe(mock_model_190, mock_declarant)

    assert isinstance(export_result, BoeExportResultDTO)
    assert export_result.model_code == "190"
    assert export_result.fiscal_year == 2026
    assert export_result.period == "0A"
    assert export_result.filename == "MODELO_190_2026_0A_B12345678.ses"
    assert export_result.records_count == 3  # 1 Tipo 1 + 2 Tipo 2

    # Cada línea mide 500 caracteres + \r\n (2 bytes) = 502 bytes * 3 = 1506 bytes
    assert export_result.total_bytes == 1506
    lines = export_result.content_raw.split("\r\n")
    assert len(lines) == 4  # Termina en CRLF, por lo que split deja último vacío
    assert lines[3] == ""
    assert len(lines[0]) == 500
    assert len(lines[1]) == 500
    assert len(lines[2]) == 500

    expected_sha256 = hashlib.sha256(export_result.content_raw.encode("utf-8")).hexdigest()
    assert export_result.sha256_checksum == expected_sha256
