import pytest
from pydantic import BaseModel
from app.domain.schemas import AnonymizationSession

class PrivacySummaryResponse(BaseModel):
    session_id: str
    total_protected_entities: int
    entities_by_type: dict[str, int]
    status: str

def test_privacy_summary_schema_generation():
    session = AnonymizationSession()
    session.register_entity("12345678Z", "NIF", 0, 9)
    session.register_entity("ES6621000418401234567891", "IBAN", 10, 34)
    session.register_entity("1.500,00 €", "IMPORTE", 35, 44)

    summary = PrivacySummaryResponse(
        session_id=session.session_id,
        total_protected_entities=len(session.entities),
        entities_by_type=session.entity_counters,
        status="protected"
    )

    assert summary.total_protected_entities == 3
    assert summary.entities_by_type["NIF"] == 1
    assert summary.entities_by_type["IBAN"] == 1
    assert summary.entities_by_type["IMPORTE"] == 1
