"""
Test de Integración para Generación de Ficheros BOE (.ses) de la AEAT (User Story 2).
Valida la exportación en formato telemático con registros de longitud fija para Modelo 303 y Modelo 130
conforme a las especificaciones oficiales de diseño de registro (sin etiquetas pseudo-XML ni corchetes).
"""

import pytest
from app.domain.services.boe_export_service import BoeExportService
from app.domain.models.billing import (
    Model303ResultDTO,
    Model130ResultDTO,
    Model111ResultDTO,
    Model115ResultDTO,
    Model390ResultDTO,
    DeclarantInfoDTO,
    BoeExportResultDTO,
)


def test_integration_generate_boe_export_model_303_positional():
    """Valida la generación de un fichero telemático oficial para importación del Modelo 303 en AEAT."""
    service = BoeExportService()

    model_303_data = Model303ResultDTO(
        fiscal_year=2026,
        quarter=1,
        base_general_21=1000.0,
        cuota_general_21=210.0,
        total_cuota_devengada=210.0,
        base_deducible_corriente=400.0,
        iva_deducible_corriente=84.0,
        total_iva_deducible=84.0,
        resultado_autoliquidacion=126.0,
        casillas={
            "01": 1000.0, "02": 21.0, "03": 210.0,
            "27": 210.0, "28": 400.0, "29": 84.0,
            "37": 84.0, "46": 126.0, "71": 126.0
        }
    )

    declarant = DeclarantInfoDTO(
        nif="12345678Z",
        name="ALFONSO ASESOR AUTONOMO SL",
        phone="912345678"
    )

    result = service.export_model_boe(
        model_code="303",
        fiscal_year=2026,
        period="1T",
        declarant_info=declarant,
        model_data=model_303_data.model_dump()
    )

    assert isinstance(result, BoeExportResultDTO)
    assert result.model_code == "303"
    assert result.fiscal_year == 2026
    assert result.period == "1T"
    assert result.declarant_nif == "12345678Z"
    assert len(result.sha256_hash) == 64

    # Validar que NO contiene etiquetas pseudo-XML ni corchetes inventados
    assert "<T3030" not in result.content_raw
    assert "<FIN_T" not in result.content_raw
    assert "[01=" not in result.content_raw

    lines = result.content_raw.splitlines()
    assert len(lines) >= 2
    # Registro Tipo 1
    assert lines[0].startswith("130320261T12345678Z")
    # Registro Tipo 2
    assert lines[1].startswith("230320261T12345678Z")


def test_integration_generate_boe_export_model_130_positional():
    """Valida la generación de fichero telemático oficial para Modelo 130."""
    service = BoeExportService()

    model_130_data = Model130ResultDTO(
        fiscal_year=2026,
        quarter=2,
        casilla_01_ingresos_acumulados=25000.0,
        casilla_02_gastos_acumulados=10000.0,
        casilla_03_rendimiento_neto=15000.0,
        casilla_04_pago_fraccionado_previo=3000.0,
        casilla_07_pagos_anteriores=1200.0,
        casilla_13_deduccion=0.0,
        casilla_19_resultado_ingresar=1800.0,
        casillas={
            "01": 25000.0, "02": 10000.0,
            "03": 15000.0, "04": 3000.0,
            "07": 1200.0, "19": 1800.0
        }
    )

    declarant = DeclarantInfoDTO(
        nif="B12345674",
        name="HOLDED SAGE COMPETITOR SL"
    )

    result = service.export_model_boe(
        model_code="130",
        fiscal_year=2026,
        period="2T",
        declarant_info=declarant,
        model_data=model_130_data.model_dump()
    )

    assert isinstance(result, BoeExportResultDTO)
    assert result.model_code == "130"
    assert "<T1300" not in result.content_raw
    lines = result.content_raw.splitlines()
    assert lines[0].startswith("113020262TB12345674")
    assert lines[1].startswith("213020262TB12345674")


def test_integration_legacy_adapter_methods():
    """Valida la compatibilidad hacia atrás de export_model_303_boe y export_model_130_boe."""
    service = BoeExportService()
    m303 = Model303ResultDTO(
        fiscal_year=2026,
        quarter=1,
        base_general_21=1000.0,
        cuota_general_21=210.0,
        total_cuota_devengada=210.0,
        resultado_autoliquidacion=210.0,
        casillas={"01": 1000.0, "03": 210.0, "46": 210.0, "71": 210.0}
    )
    raw = service.export_model_303_boe(m303, {"nif": "12345678Z", "name": "TEST"})
    assert isinstance(raw, str)
    assert raw.startswith("130320261T")
    assert "<T3030" not in raw
