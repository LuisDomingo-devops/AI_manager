"""
Pruebas de integración para la exportación oficial BOE del Modelo 180 (.ses).
Verifica:
1. Longitud exacta de 500 caracteres por registro con separador CRLF.
2. Formato del nombre de archivo según recomendación I1: MODELO_180_{fiscal_year}_0A_{declarant_nif}.ses
3. Integridad criptográfica SHA-256.
4. Registro y custodia automática en tax_declarations_ledger.
5. Invocación telemática vía endpoint de la API.
"""

import hashlib
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models.billing import (
    Model180ResultDTO,
    Model180PerceptorDTO,
    InmuebleArrendadoDTO,
    DeclarantInfoDTO
)
from app.domain.services.boe_export_service import BoeExportService
from app.domain.services.tax_ledger_service import TaxLedgerService


@pytest.fixture
def sample_data_180():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="PASEO DE LA CASTELLANA",
        numero="100",
        municipio="MADRID",
        codigo_postal="28046",
        codigo_provincia="28"
    )
    perceptor = Model180PerceptorDTO(
        nif="B88888888",
        name="ARRENDAMIENTOS URBANOS SA",
        base_retencion=10000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=1900.0,
        inmueble=inmueble
    )
    model_data = Model180ResultDTO(
        fiscal_year=2026,
        total_perceptores=1,
        total_base_retenciones=10000.0,
        total_retenciones_practicadas=1900.0,
        perceptores=[perceptor]
    )
    declarant = DeclarantInfoDTO(
        nif="B87654321",
        name="EMPRESA DECLARANTE SL",
        phone="910000000",
        contact_person="ANA GOMEZ"
    )
    return model_data, declarant


def test_export_model_180_boe_service_direct(sample_data_180):
    """Verifica la exportación directa mediante BoeExportService."""
    model_data, declarant = sample_data_180
    service = BoeExportService()

    res = service.export_model_180_boe(model_data, declarant)

    # Verificación I1: Nombre canónico de archivo
    expected_filename = f"MODELO_180_2026_0A_B87654321.ses"
    assert res.filename == expected_filename
    assert res.model_code == "180"
    assert res.fiscal_year == 2026
    assert res.period == "0A"
    assert res.records_count == 2

    # Verificación CRLF y 500 caracteres por línea
    lines = res.content_raw.split("\r\n")
    assert lines[-1] == ""  # Termina en CRLF
    content_lines = lines[:-1]
    assert len(content_lines) == 2
    for idx, line in enumerate(content_lines):
        assert len(line) == 500, f"Línea {idx+1} tiene longitud {len(line)}, esperada 500"

    # Verificación checksum SHA-256
    calc_sha = hashlib.sha256(res.content_raw.encode("utf-8")).hexdigest()
    assert res.sha256_checksum == calc_sha


def test_export_model_180_boe_api_and_custody_recording(sample_data_180):
    """Verifica el endpoint POST /api/v1/tax/models/180/export-boe y el auto-registro en ledger."""
    model_data, declarant = sample_data_180
    client = TestClient(app)
    headers = {"X-API-Key": "test_api_key_default"}

    payload = {
        "fiscal_year": 2026,
        "period": "0A",
        "declarant_info": declarant.model_dump(),
        "model_data": model_data.model_dump(),
        "auto_record_ledger": True
    }

    response = client.post("/api/v1/tax/models/180/export-boe", json=payload, headers=headers)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["model_code"] == "180"
    assert data["filename"] == "MODELO_180_2026_0A_B87654321.ses"
    assert data["records_count"] == 2
    assert "content_raw" in data

    # Comprobar que se guardó en el ledger
    ledger = TaxLedgerService()
    filings = ledger.list_declarations(model_code="180", fiscal_year=2026)
    assert len(filings) >= 1
    latest = filings[0]
    assert latest.model_code == "180"
    assert latest.declarant_nif == "B87654321"
    assert latest.filing_status == "EXPORTED"
