"""
Pruebas unitarias de serialización del diseño de registro telemático oficial BOE (.ses)
para el Modelo 347, conforme a la Orden EHA/3012/2008 y Orden HAP/2194/2013.
Verifica que cada registro mida exactamente 500 caracteres y que los campos numéricos y claves
se formateen según las especificaciones técnicas oficiales.
"""

import pytest
from app.domain.models.billing import (
    Model347ResultDTO,
    Model347DeclaredDTO,
    DeclarantInfoDTO
)
from app.domain.services.boe_export_service import BoeExportService


def test_modelo_347_boe_record_length_exactly_500_chars(sample_model_347_result, sample_declarant_info):
    """
    Verifica que el Registro Tipo 1 y todos los Registros Tipo 2 midan exactamente 500 caracteres.
    """
    service = BoeExportService()
    boe_result = service.export_model_347_boe(
        model_data=sample_model_347_result,
        declarant_info=sample_declarant_info
    )

    lines = boe_result.content_raw.splitlines()
    assert len(lines) == 3  # 1 Registro Tipo 1 + 2 Registros Tipo 2

    for idx, line in enumerate(lines):
        assert len(line) == 500, f"La línea {idx + 1} mide {len(line)} caracteres (se requieren exactamente 500)"


def test_modelo_347_boe_type_1_fields(sample_model_347_result, sample_declarant_info):
    """
    Verifica las posiciones canónicas del Registro Tipo 1 (Declarante).
    """
    service = BoeExportService()
    t1 = service.format_model_347_type_1(
        model_data=sample_model_347_result,
        declarant_info=sample_declarant_info
    )

    assert len(t1) == 500
    assert t1[0] == "1"                        # Tipo registro
    assert t1[1:4] == "347"                    # Modelo
    assert t1[4:8] == "2026"                   # Ejercicio
    assert t1[8:17] == "B87654321"             # NIF declarante
    assert t1[57] == "T"                       # Soporte telemático
    # Posiciones 135-143 (0-indexed [134:143]): Total declarados (9 dígitos con ceros)
    assert t1[134:143] == "000000002"
    # Posiciones 144-159 (0-indexed [143:159]): Importe total operaciones (37000.00 -> ' 000000003700000')
    assert t1[143:159] == " 000000003700000"


def test_modelo_347_boe_type_2_fields(sample_model_347_purchase_declared, sample_declarant_info):
    """
    Verifica las posiciones canónicas del Registro Tipo 2 (Declarado).
    """
    service = BoeExportService()
    t2 = service.format_model_347_type_2(
        declared=sample_model_347_purchase_declared,
        fiscal_year=2026,
        declarant_nif="B87654321"
    )

    assert len(t2) == 500
    assert t2[0] == "2"                        # Tipo registro
    assert t2[1:4] == "347"                    # Modelo
    assert t2[4:8] == "2026"                   # Ejercicio
    assert t2[8:17] == "B87654321"             # NIF declarante
    assert t2[17:26] == "B12345674"            # NIF declarado
    assert t2[75] == "D"                       # Tipo de hoja: 'D' (Declarados)
    assert t2[76:78] == "28"                   # Provincia
    assert t2[78] == "A"                       # Clave de operación: 'A' (Compras)
    # Posiciones 80-95 (0-indexed [79:95]): Total anual 12000.00 -> ' 000000001200000'
    assert t2[79:95] == " 000000001200000"
    # Posiciones 97-112 (0-indexed [96:112]): 1T 3000.00
    assert t2[96:112] == " 000000000300000"
    # Posiciones 113-128 (0-indexed [112:128]): 2T 3000.00
    assert t2[112:128] == " 000000000300000"
    # Posiciones 129-144 (0-indexed [128:144]): 3T 3000.00
    assert t2[128:144] == " 000000000300000"
    # Posiciones 145-160 (0-indexed [144:160]): 4T 3000.00
    assert t2[144:160] == " 000000000300000"
    # Posiciones 161-176 (0-indexed [160:176]): Cobros metálico 0.00 -> ' 000000000000000'
    assert t2[160:176] == " 000000000000000"


def test_modelo_347_boe_cash_amount_in_type_2(sample_model_347_sales_declared):
    """
    Verifica que el importe percibido en metálico > 6.000 € se serialice en las posiciones 161-176.
    """
    service = BoeExportService()
    t2 = service.format_model_347_type_2(
        declared=sample_model_347_sales_declared,
        fiscal_year=2026,
        declarant_nif="B87654321"
    )

    # Posiciones 161-176 (0-indexed [160:176]): 8500.00 € -> ' 000000000850000'
    assert t2[160:176] == " 000000000850000"
    assert t2[78] == "B"  # Clave de ventas
