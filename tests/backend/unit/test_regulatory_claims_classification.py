import pytest
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.tgss_affiliation_service import TgssAffiliationService

def test_verifactu_declaration_dossier_claims_classification():
    """
    Verifica las secciones 14 y 15 del Discovery Contract:
    1. La Declaración Responsable debe emitirse como borrador ('draft'), nunca 'ok' como homologación definitiva.
    2. Debe clasificarse explícitamente como 'UNVERIFIED'.
    3. No debe afirmar categóricamente que 'cumple íntegramente'.
    """
    dossier = VerifactuService.get_compliance_declaration_dossier(client_id="test_client_reg")

    assert dossier["declaration_state"] == "draft", (
        f"La declaración responsable debe tener estado técnico 'draft', obtenido: {dossier.get('declaration_state')}"
    )
    assert dossier.get("regulatory_status") == "UNVERIFIED", (
        f"El claim regulatorio debe clasificarse como 'UNVERIFIED', obtenido: {dossier.get('regulatory_status')}"
    )
    statement_lower = dossier.get("statement", "").lower()
    assert "cumple íntegramente" not in statement_lower, (
        "La declaración responsable no puede afirmar que 'cumple íntegramente' sin certificación formal de la AEAT."
    )

def test_tgss_afi_generation_regulatory_status():
    """
    Verifica que la generación de ficheros AFI no afirme homologación oficial y exponga regulatory_status='UNVERIFIED'.
    """
    fake_employee = {
        "id": 1,
        "full_name": "Juan Perez",
        "nif": "12345678Z",
        "nss": "281234567890",
        "start_date": "2026-10-01",
        "contract_type": "100",
        "contribution_group": 1
    }
    result = TgssAffiliationService.generate_alta_afi(fake_employee)

    assert result.get("regulatory_status") == "UNVERIFIED", (
        f"El fichero AFI debe clasificarse con regulatory_status='UNVERIFIED', obtenido: {result.get('regulatory_status')}"
    )
