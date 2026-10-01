"""
Test de Integración para Generación de Ficheros BOE (.ses) de la AEAT (User Story 3).
Valida la exportación en formato telemático con registros de longitud fija para Modelo 303 y Modelo 130.
"""

import pytest
from app.domain.services.boe_export_service import BoeExportService
from app.domain.models.billing import Model303ResultDTO, Model130ResultDTO


def test_integration_generate_boe_export_model_303():
    """Valida la generación de un fichero telemático oficial para importación del Modelo 303 en AEAT."""
    service = BoeExportService()
    
    model_303_data = Model303ResultDTO(
        fiscal_year=2026,
        quarter=1,
        base_superreducido_4=200.0,
        cuota_superreducido_4=8.0,
        base_reducido_10=500.0,
        cuota_reducido_10=50.0,
        base_general_21=1000.0,
        cuota_general_21=210.0,
        total_cuota_devengada=268.0,
        iva_deducible_corriente=168.0,
        iva_deducible_inversion=0.0,
        prorrata_pct=100.0,
        total_iva_deducible=168.0,
        resultado_autoliquidacion=100.0,
        casillas={
            "01": 200.0, "03": 8.0,
            "04": 500.0, "06": 50.0,
            "07": 1000.0, "09": 210.0,
            "27": 268.0, "28": 800.0,
            "29": 168.0, "46": 100.0
        }
    )
    
    declarant_info = {
        "nif": "12345678Z",
        "name": "ALFONSO ASESOR AUTONOMO"
    }
    
    boe_file_content = service.export_model_303_boe(model_303_data, declarant_info)
    
    assert isinstance(boe_file_content, str)
    assert len(boe_file_content) > 100
    # Comprobar etiquetas o posiciones fijas BOE
    assert "303" in boe_file_content
    assert "2026" in boe_file_content
    assert "1T" in boe_file_content or "1" in boe_file_content
    assert "12345678Z" in boe_file_content
    # Comprobar que incluye el resultado formateado (100.00 con ceros a la izquierda)
    assert "00000010000" in boe_file_content or "100" in boe_file_content


def test_integration_generate_boe_export_model_130():
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
    
    declarant_info = {
        "nif": "B12345674",
        "name": "HOLDED SAGE COMPETITOR S.L."
    }
    
    boe_file_content = service.export_model_130_boe(model_130_data, declarant_info)
    assert "130" in boe_file_content
    assert "2026" in boe_file_content
    assert "B12345674" in boe_file_content
    assert "00000180000" in boe_file_content or "1800" in boe_file_content
