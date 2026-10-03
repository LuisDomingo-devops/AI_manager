"""
Pruebas de integración de exportación oficial BOE telemática (.ses) para el Modelo 347.
Verifica la creación del archivo oficial con hash SHA-256 y nombre normalizado de la AEAT.
"""

import hashlib
import pytest
from app.domain.services.boe_export_service import BoeExportService
from app.domain.models.billing import (
    Model347ResultDTO,
    DeclarantInfoDTO
)


def test_modelo_347_boe_export_integration(sample_model_347_result, sample_declarant_info):
    """
    Verifica que export_model_347_boe produzca un BoeExportResultDTO válido con hash SHA-256 real,
    nombre de fichero .ses y registros de 500 caracteres.
    """
    service = BoeExportService()
    result = service.export_model_347_boe(
        model_data=sample_model_347_result,
        declarant_info=sample_declarant_info
    )

    assert result.model_code == "347"
    assert result.fiscal_year == 2026
    assert result.period == "0A"
    assert result.file_name == "347_2026_B87654321.ses"
    assert result.total_lines == 3
    assert len(result.record_type_1) == 500
    assert len(result.records_type_2) == 2
    for r2 in result.records_type_2:
        assert len(r2) == 500

    expected_hash = hashlib.sha256(result.content_raw.encode("utf-8")).hexdigest()
    assert result.sha256_hash == expected_hash


def test_generic_export_model_boe_dispatches_347(sample_model_347_result, sample_declarant_info):
    """
    Verifica que el dispatcher general export_model_boe soporte model_code='347'.
    """
    service = BoeExportService()
    result = service.export_model_boe(
        model_code="347",
        fiscal_year=2026,
        period="0A",
        declarant_info=sample_declarant_info,
        model_data=sample_model_347_result
    )

    assert result.model_code == "347"
    assert result.total_lines == 3
    assert result.record_type_1.startswith("13472026B87654321")
