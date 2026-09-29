"""
QA Suite: Regulatory Claims Audit and False Certainty Verification.
Verifica que ningún servicio de cumplimiento o herramienta de asesor fiscal emita claims categóricos
de homologación oficial o cumplimiento íntegro sin la clasificación UNVERIFIED requerida por el Contrato de Discovery.
"""
import pytest
from app.domain.services.verifactu_service import VerifactuService
from app.tools.server.advisor_tools import get_compliance_declaration_dossier as advisor_compliance_dossier
from app.domain.services.tgss_affiliation_service import TgssAffiliationService

def test_qa_regulatory_declaration_integrity():
    """Auditoría QA: La declaración técnica generada no debe afirmar homologación oficial definitiva."""
    dossier = VerifactuService.get_compliance_declaration_dossier()
    
    # 1. Metadatos de clasificación
    assert dossier.get("regulatory_status") == "UNVERIFIED"
    assert dossier.get("status") == "ok"
    assert dossier.get("declaration_state") == "draft"
    evidencias = dossier.get("expediente_evidencias_tecnicas", {})
    assert evidencias.get("homologacion_oficial_aeat") == "UNVERIFIED_PENDING_AEAT_VALIDATION"
    
    # 2. Análisis del texto de la declaración
    declaration_text = dossier.get("statement", "")
    assert "BORRADOR TÉCNICO" in declaration_text
    assert "PENDIENTE DE HOMOLOGACIÓN OFICIAL" in declaration_text
    
    # Prohibición expresa de claims absolutos engañosos
    assert "cumple íntegramente con todos los requisitos establecidos en la Ley 58/2003" not in declaration_text
    assert "100% certificado" not in declaration_text.lower()
    assert "homologado por la aeat" not in declaration_text.lower()

@pytest.mark.asyncio
async def test_qa_advisor_tools_regulatory_integrity():
    """Auditoría QA: AdvisorTools no debe presentar la declaración técnica como cumplimiento certificado."""
    result = await advisor_compliance_dossier()
    
    assert result.get("status") == "ok"
    assert result.get("declaration_state") == "draft"
    assert result.get("regulatory_status") == "UNVERIFIED"
    
    content = result.get("content", "")
    assert "BORRADOR TÉCNICO" in content
    assert "cumple íntegramente" not in content

def test_qa_tgss_afi_records_are_unverified():
    """Auditoría QA: Las altas y bajas AFI no deben declararse verificadas ni enviadas oficialmente."""
    fake_employee = {
        "id": 999,
        "full_name": "QA Employee",
        "nif": "12345678Z",
        "nss": "281234567890",
        "start_date": "2026-10-01",
        "contract_type": "100",
        "contribution_group": 1
    }
    res_alta = TgssAffiliationService.generate_alta_afi(fake_employee)
    assert res_alta["regulatory_status"] == "UNVERIFIED"
    assert "warning" in res_alta
    assert "requiere homologación formal siltra" in res_alta["warning"].lower()
    
    res_baja = TgssAffiliationService.generate_baja_afi(
        fake_employee,
        termination_type="DESPIDO_DISCIPLINARIO",
        termination_date="2026-10-15"
    )
    assert res_baja["regulatory_status"] == "UNVERIFIED"
    assert "warning" in res_baja
    assert "requiere homologación formal siltra" in res_baja["warning"].lower()
