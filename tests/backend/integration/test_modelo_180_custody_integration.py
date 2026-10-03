"""
Pruebas de integración de custodia legal obligatoria por 5 años (Arts. 66 a 70 LGT)
para el Modelo 180 en tax_declarations_ledger.
"""

from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.models.billing import (
    Model180ResultDTO,
    Model180PerceptorDTO,
    InmuebleArrendadoDTO,
    DeclarantInfoDTO
)
from app.domain.services.tax_ledger_service import TaxLedgerService
from app.domain.services.annual_tax_service import AnnualTaxService


@pytest.fixture
def sample_modelo_180_data():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="ALCALA",
        numero="50",
        municipio="MADRID",
        codigo_postal="28014",
        codigo_provincia="28"
    )
    perceptor = Model180PerceptorDTO(
        nif="B99999999",
        name="INMOBILIARIA PATRIMONIAL SA",
        base_retencion=8000.0,
        porcentaje_retencion=19.0,
        retencion_practicada=1520.0,
        inmueble=inmueble
    )
    model_data = Model180ResultDTO(
        fiscal_year=2026,
        total_perceptores=1,
        total_base_retenciones=8000.0,
        total_retenciones_practicadas=1520.0,
        perceptores=[perceptor]
    )
    declarant = DeclarantInfoDTO(
        nif="B87654321",
        name="EMPRESA DECLARANTE SL",
        phone="915555555"
    )
    return model_data, declarant


def test_custody_retention_date_5_years_and_retrieval(sample_modelo_180_data):
    """Verifica que el Modelo 180 se archive con retention_until_date exactamente a 5 años naturales."""
    model_data, declarant = sample_modelo_180_data
    annual_service = AnnualTaxService()

    # Ejecutar archivo y custodia legal
    filing = annual_service.file_and_custody_model_180(
        model_180_result=model_data,
        declarant_info=declarant,
        tenant_id="custody_180_tenant"
    )

    assert filing.id is not None
    assert filing.tenant_id == "custody_180_tenant"
    assert filing.model_code == "180"
    assert filing.fiscal_year == 2026
    assert filing.period == "0A"
    assert filing.declarant_nif == "B87654321"
    assert filing.filing_status == "CALCULATED"

    # Verificar 5 años exactos de retención legal (Art. 66 LGT)
    f_date = datetime.strptime(filing.filing_date, "%Y-%m-%d %H:%M:%S")
    r_date = datetime.strptime(filing.retention_until_date, "%Y-%m-%d %H:%M:%S")
    assert r_date.year == f_date.year + 5
    assert r_date.month == f_date.month
    assert r_date.day == f_date.day

    # Recuperar desde el ledger
    ledger = TaxLedgerService()
    retrieved = ledger.get_declaration_by_id(filing.id)
    assert retrieved is not None
    assert retrieved.sha256_hash == filing.sha256_hash
    assert len(retrieved.boe_file_content) > 0


def test_file_and_custody_endpoint_api(sample_modelo_180_data):
    """Verifica el endpoint POST /api/v1/tax/models/180/file-and-custody."""
    model_data, declarant = sample_modelo_180_data
    client = TestClient(app)
    headers = {"X-API-Key": "test_api_key_default"}

    payload = {
        "fiscal_year": 2026,
        "tenant_id": "default",
        "declarant_info": declarant.model_dump(),
        "model_180_data": model_data.model_dump()
    }

    res = client.post("/api/v1/tax/models/180/file-and-custody", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    audit = res.json()

    assert audit["model_code"] == "180"
    assert audit["declarant_nif"] == "B87654321"
    assert audit["filing_status"] == "CALCULATED"
    assert "retention_until_date" in audit
