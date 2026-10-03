"""
Pruebas de integración para la custodia legal obligatoria e inmutable de 5 años
del Modelo 347 en tax_declarations_ledger (Ley 58/2003 LGT).
"""

from datetime import datetime
import pytest
from app.adapters.memory.memory import _get_connection
from app.domain.services.annual_tax_service import AnnualTaxService
from app.domain.services.tax_ledger_service import TaxLedgerService
from app.domain.exceptions import TaxRetentionPolicyViolationError


def test_modelo_347_file_and_custody_5_years(sample_model_347_result, sample_declarant_info):
    """
    Verifica que file_and_custody_model_347 archive el Modelo 347 con su fichero telemático .ses,
    su hash SHA-256 inmutable y fije la fecha de retención legal en exactamente 5 años.
    """
    with _get_connection() as conn:
        conn.execute("DELETE FROM tax_declarations_ledger WHERE fiscal_year = 2026 AND model_code = '347'")
        conn.commit()

    service = AnnualTaxService()
    audit_record = service.file_and_custody_model_347(
        model_347=sample_model_347_result,
        declarant_info=sample_declarant_info,
        filing_status="CALCULATED",
        aeat_csv="CSV347-2026-TEST"
    )

    assert audit_record.id is not None
    assert audit_record.model_code == "347"
    assert audit_record.fiscal_year == 2026
    assert audit_record.period == "0A"
    assert audit_record.declarant_nif == "B87654321"
    assert audit_record.aeat_csv == "CSV347-2026-TEST"
    assert len(audit_record.sha256_hash) == 64
    assert len(audit_record.boe_file_content) > 0

    # Comprobación de retención legal de 5 años (LGT arts. 29.2 y 66-70)
    filing_dt = datetime.strptime(audit_record.filing_date, "%Y-%m-%d %H:%M:%S")
    retention_dt = datetime.strptime(audit_record.retention_until_date, "%Y-%m-%d %H:%M:%S")
    years_diff = retention_dt.year - filing_dt.year
    assert years_diff == 5

    # Comprobación de inmutabilidad: no se permite borrar dentro del plazo de 5 años
    ledger_service = TaxLedgerService()
    with pytest.raises(TaxRetentionPolicyViolationError, match="custodia legal obligatoria de 5 años"):
        ledger_service.assert_can_delete(audit_record.id)

    # Comprobación de recuperación
    retrieved = ledger_service.get_declaration_by_id(audit_record.id)
    assert retrieved is not None
    assert retrieved.casillas_payload["total_declarados"] == 2
    assert retrieved.casillas_payload["total_operaciones"] == 37000.00
    assert retrieved.casillas_payload["total_metalico"] == 8500.00
