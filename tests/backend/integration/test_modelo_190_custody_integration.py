"""
Pruebas de integración de custodia legal de 5 años y bloqueo de borrado para el Modelo 190.
Conforme al art. 29.2 de la Ley General Tributaria (Ley 58/2003).
"""

from datetime import datetime
import pytest
from app.domain.models.billing import (
    Model190ResultDTO,
    Model190PerceptorDTO,
    DeclarantInfoDTO,
    TaxDeclarationAuditDTO
)
from app.domain.services.annual_tax_service import AnnualTaxService
from app.domain.services.tax_ledger_service import TaxLedgerService
from app.domain.exceptions import TaxRetentionPolicyViolationError
from app.adapters.memory.memory import _get_connection


@pytest.fixture
def clean_ledger():
    """Limpia registros previos del Modelo 190 para el año 2026."""
    with _get_connection() as conn:
        conn.execute("DELETE FROM tax_declarations_ledger WHERE model_code = '190' AND fiscal_year = 2026")
        conn.commit()
    yield
    with _get_connection() as conn:
        conn.execute("DELETE FROM tax_declarations_ledger WHERE model_code = '190' AND fiscal_year = 2026")
        conn.commit()


def test_file_and_custody_model_190_success(clean_ledger):
    """Verifica que el Modelo 190 se custodia con período 0A, hash SHA-256 y retención a 5 años."""
    service = AnnualTaxService()
    ledger_service = TaxLedgerService()

    perceptor = Model190PerceptorDTO(
        nif="12345678Z",
        name="GARCIA PEREZ, JUAN",
        province_code="28",
        clave="A",
        subclave="  ",
        percepciones_dinerarias=24000.0,
        retenciones_practicadas=3600.0,
        percepciones_especie_valoracion=0.0,
        percepciones_especie_ingresos_a_cuenta=0.0,
        percepciones_especie_repercutidos=0.0
    )

    model_190 = Model190ResultDTO(
        fiscal_year=2026,
        declarant_nif="B12345678",
        total_perceptores=1,
        total_percepciones_dinerarias=24000.0,
        total_retenciones_practicadas=3600.0,
        total_percepciones_especie=0.0,
        total_ingresos_a_cuenta=0.0,
        total_percepciones_global=24000.0,
        perceptores=[perceptor]
    )

    declarant = DeclarantInfoDTO(
        nif="B12345678",
        name="CONSULTORA FISCAL DEL SUR SL",
        phone="954123456"
    )

    # Custodiar
    audit_record = service.file_and_custody_model_190(
        model_190=model_190,
        declarant_info=declarant,
        tenant_id="tenant_190_test"
    )

    assert isinstance(audit_record, TaxDeclarationAuditDTO)
    assert audit_record.id is not None
    assert audit_record.model_code == "190"
    assert audit_record.fiscal_year == 2026
    assert audit_record.period == "0A"
    assert audit_record.declarant_nif == "B12345678"
    assert audit_record.filing_status == "CALCULATED"
    assert len(audit_record.sha256_hash) == 64
    assert len(audit_record.boe_file_content) > 0

    # Verificar cálculo legal de 5 años
    filing_year = int(audit_record.filing_date[:4])
    retention_year = int(audit_record.retention_until_date[:4])
    assert retention_year == filing_year + 5

    # Verificar que el borrado dentro del período legal está bloqueado
    with pytest.raises(TaxRetentionPolicyViolationError) as exc_info:
        ledger_service.assert_can_delete(audit_record.id)

    assert "custodia legal obligatoria de 5 años" in str(exc_info.value)
