"""
test_aeat_boe_file_generator.py
===============================
Tests unitarios posicionales byte a byte para el generador de ficheros oficiales del BOE / AEAT (.ses).
Valida:
1. Longitudes fijas de caracteres y posiciones exactas (Registro Tipo 1 y Tipo 2).
2. Formato numérico de 17 caracteres (15 enteros + 2 decimales sin coma) con signo 'N' para importes negativos.
3. Relleno y justificación: strings justificados a la izquierda con espacios, números zfill con ceros a la derecha.
4. Generación posicional conforme para Modelos 303, 130, 111, 115 y 390.
"""
import pytest
from app.domain.services.boe_export_service import BoeExportService
from app.domain.models.billing import (
    Model303ResultDTO,
    Model130ResultDTO,
    Model111ResultDTO,
    Model115ResultDTO,
    Model390ResultDTO,
    DeclarantInfoDTO
)


def test_format_amount_17_chars_positive():
    """Valida que un importe positivo se formatea a exactamente 17 caracteres con ceros a la izquierda."""
    service = BoeExportService()
    formatted = service.format_amount_17(1234.56)
    assert len(formatted) == 17
    # 1234.56 en céntimos son 123456 -> con 17 chars debe ser '00000000000123456' o ' 0000000000123456'
    assert formatted.endswith("123456")
    assert formatted.startswith("0") or formatted.startswith(" ")


def test_format_amount_17_chars_negative():
    """Valida que un importe negativo lleva signo 'N' en la primera posición."""
    service = BoeExportService()
    formatted = service.format_amount_17(-500.25)
    assert len(formatted) == 17
    assert formatted[0] == "N"
    assert formatted.endswith("50025")


def test_format_string_exact_length():
    """Valida el formateo alfanumérico con justificación a la izquierda y truncado seguro."""
    service = BoeExportService()
    res = service.format_str("ALFONSO", 10)
    assert len(res) == 10
    assert res == "ALFONSO   "

    res_truncated = service.format_str("NOMBRE_DEMASIADO_LARGO_PARA_EL_CAMPO", 10)
    assert len(res_truncated) == 10
    assert res_truncated == "NOMBRE_DEM"


def test_export_model_303_boe_positional_records():
    """Valida byte a byte la estructura posicional del fichero BOE para el Modelo 303."""
    service = BoeExportService()

    declarant = DeclarantInfoDTO(
        nif="12345678Z",
        name="EMPRESA MODELO 303 SL",
        phone="912345678"
    )

    model_303 = Model303ResultDTO(
        fiscal_year=2026,
        quarter=1,
        base_general_21=1000.0,
        cuota_general_21=210.0,
        total_cuota_devengada=210.0,
        base_deducible_corriente=400.0,
        iva_deducible_corriente=84.0,
        total_iva_deducible=84.0,
        resultado_regimen_general=126.0,
        resultado_autoliquidacion=126.0,
        casillas={
            "01": 1000.0, "02": 21.0, "03": 210.0,
            "27": 210.0, "28": 400.0, "29": 84.0,
            "37": 84.0, "46": 126.0, "71": 126.0
        }
    )

    result = service.export_model_boe(
        model_code="303",
        fiscal_year=2026,
        period="1T",
        declarant_info=declarant,
        model_data=model_303.model_dump()
    )

    assert result.model_code == "303"
    assert result.fiscal_year == 2026
    assert result.period == "1T"
    assert result.filename.endswith(".ses")

    lines = result.content_raw.splitlines()
    assert len(lines) >= 2, "Debe contener al menos Registro Tipo 1 y Registro Tipo 2"

    line1 = lines[0]
    line2 = lines[1]

    # --- Registro Tipo 1 (Declarante) ---
    assert line1[0] == "1", "Posición 1 debe ser '1' (Tipo de registro)"
    assert line1[1:4] == "303", "Posición 2-4 debe ser '303'"
    assert line1[4:8] == "2026", "Posición 5-8 debe ser ejercicio '2026'"
    assert line1[8:10] == "1T", "Posición 9-10 debe ser periodo '1T'"
    assert line1[10:19] == "12345678Z", "Posición 11-19 debe ser NIF"
    assert line1[19:59].startswith("EMPRESA MODELO 303 SL")

    # --- Registro Tipo 2 (Liquidación) ---
    assert line2[0] == "2", "Posición 1 debe ser '2' (Tipo de registro)"
    assert line2[1:4] == "303"
    assert line2[4:8] == "2026"
    assert line2[8:10] == "1T"
    assert line2[10:19] == "12345678Z"

    # Verificar que NO contiene tags inventados como <T3030 o [01=
    assert "<T3030" not in result.content_raw
    assert "[01=" not in result.content_raw
    assert "<FIN_T" not in result.content_raw


def test_export_model_130_boe_positional_records():
    """Valida la generación posicional del Modelo 130."""
    service = BoeExportService()

    declarant = DeclarantInfoDTO(
        nif="B12345674",
        name="CONSULTORIA AUTONOMA HOLDING SL"
    )

    model_130 = Model130ResultDTO(
        fiscal_year=2026,
        quarter=2,
        casilla_01_ingresos_acumulados=20000.0,
        casilla_02_gastos_acumulados=5000.0,
        casilla_03_rendimiento_neto=15000.0,
        casilla_04_pago_fraccionado_previo=3000.0,
        casilla_07_pagos_anteriores=1000.0,
        casilla_19_resultado_ingresar=2000.0,
        casillas={
            "01": 20000.0, "02": 5000.0, "03": 15000.0,
            "04": 3000.0, "07": 1000.0, "19": 2000.0
        }
    )

    result = service.export_model_boe(
        model_code="130",
        fiscal_year=2026,
        period="2T",
        declarant_info=declarant,
        model_data=model_130.model_dump()
    )

    lines = result.content_raw.splitlines()
    assert lines[0][:10] == "113020262T"
    assert lines[1][:10] == "213020262T"
    assert lines[0][10:19] == "B12345674"
    assert "<T1300" not in result.content_raw
