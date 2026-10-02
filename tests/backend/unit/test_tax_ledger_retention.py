"""
test_tax_ledger_retention.py
============================
Pruebas unitarias para la política legal de retención y custodia de 5 años:
- Cálculo determinista de retention_until_date (fecha de cálculo + 5 años).
- Manejo correcto de años bisiestos.
- Cálculo de integridad mediante hash SHA-256.
- Prevención de purgado antes del vencimiento legal (TaxRetentionPolicyViolationError).
"""
import pytest
from datetime import datetime
from app.domain.services.tax_ledger_service import TaxLedgerService
from app.domain.exceptions import TaxRetentionPolicyViolationError
from app.domain.models.billing import TaxDeclarationAuditDTO


def test_retention_date_calculation_5_years():
    """Valida que la fecha de retención se calcula exactamente a 5 años desde la fecha base."""
    service = TaxLedgerService()
    base = datetime(2026, 4, 20, 10, 30, 0)
    retention_str = service.calculate_retention_date(base)
    assert retention_str == "2031-04-20 10:30:00"


def test_retention_date_calculation_leap_year():
    """Valida el manejo robusto de años bisiestos (ejemplo 29 de febrero de 2024 a 2029)."""
    service = TaxLedgerService()
    leap_date = datetime(2024, 2, 29, 12, 0, 0)
    retention_str = service.calculate_retention_date(leap_date)
    # Al no ser bisiesto 2029, pasa a 28 de febrero
    assert retention_str == "2029-02-28 12:00:00"


def test_compute_sha256_determinism():
    """Valida que el cálculo de hash SHA-256 es determinista y coincide con la función estándar."""
    service = TaxLedgerService()
    content = "130320261T12345678ZCONTENIDO_OFICIAL_BOE"
    h1 = service.compute_sha256(content)
    h2 = service.compute_sha256(content)
    assert len(h1) == 64
    assert h1 == h2
    assert service.compute_sha256(content + "X") != h1


def test_assert_can_delete_raises_policy_violation(monkeypatch):
    """Valida que intentar eliminar una declaración custodiada dentro de los 5 años lanza excepción."""
    service = TaxLedgerService()
    dto = TaxDeclarationAuditDTO(
        id=1,
        tenant_id="default",
        model_code="303",
        fiscal_year=2026,
        period="1T",
        declarant_nif="12345678Z",
        declarant_name="EMPRESA SL",
        casillas_payload={"01": 1000.0, "03": 210.0},
        boe_file_content="BOE_RAW_CONTENT",
        sha256_hash="abcdef123456",
        filing_status="EXPORTED",
        filing_date="2026-04-20 10:00:00",
        retention_until_date="2031-04-20 10:00:00",
        created_at="2026-04-20 10:00:00"
    )

    monkeypatch.setattr(service, "get_declaration_by_id", lambda fid: dto)

    with pytest.raises(TaxRetentionPolicyViolationError) as exc_info:
        service.assert_can_delete(1)

    err = exc_info.value
    assert "5 años" in err.message or "custodia" in err.message.lower()
    assert err.filing_id == "1"
