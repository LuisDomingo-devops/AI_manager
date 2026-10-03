"""
test_modelo_190_qa.py
======================
Suite de QA para la validación y automatización asistida del Modelo 190 en Mozilla Firefox.
Verifica:
1. Generación de exportación telemática oficial BOE del Modelo 190 e integración con FirefoxFilingService.
2. Uso exclusivo del navegador Mozilla Firefox y prohibición estricta de Google Chrome.
3. Parada del flujo asistido en estado AWAITING_USER_SIGNATURE (Human-in-the-Loop) para firma manual.
4. Rechazo e interrupción ante ficheros BOE corruptos o no conformes.
"""

import pytest
from app.domain.models.billing import (
    Model190ResultDTO,
    Model190PerceptorDTO,
    DeclarantInfoDTO,
    FilingSessionStatus
)
from app.domain.services.boe_export_service import BoeExportService
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.exceptions import FirefoxFilingError


@pytest.fixture
def sample_modelo_190_and_boe():
    perceptor_1 = Model190PerceptorDTO(
        nif="12345678Z",
        name="GARCIA PEREZ, JUAN",
        province_code="28",
        clave="A",
        subclave="  ",
        percepciones_dinerarias=28000.0,
        retenciones_practicadas=4200.0,
        percepciones_especie_valoracion=1200.0,
        percepciones_especie_ingresos_a_cuenta=180.0,
        percepciones_especie_repercutidos=180.0
    )
    perceptor_2 = Model190PerceptorDTO(
        nif="87654321B",
        name="LOPEZ ASESORES SL",
        province_code="08",
        clave="G",
        subclave="01",
        percepciones_dinerarias=5000.0,
        retenciones_practicadas=750.0
    )

    model_190 = Model190ResultDTO(
        fiscal_year=2026,
        declarant_nif="B12345678",
        total_perceptores=2,
        total_percepciones_dinerarias=33000.0,
        total_retenciones_practicadas=4950.0,
        total_percepciones_especie=1200.0,
        total_ingresos_a_cuenta=180.0,
        total_percepciones_global=34200.0,
        perceptores=[perceptor_1, perceptor_2]
    )

    declarant = DeclarantInfoDTO(
        nif="B12345678",
        name="INNOVACIONES FISCALES SL",
        phone="912345678"
    )

    boe_service = BoeExportService()
    boe_result = boe_service.export_model_190_boe(model_190, declarant)
    return model_190, declarant, boe_result


@pytest.mark.asyncio
async def test_qa_modelo_190_firefox_workflow_success(sample_modelo_190_and_boe):
    """Verifica que el flujo asistido del Modelo 190 en Firefox alcanza la previsualización y espera de firma."""
    model_190, declarant, boe_result = sample_modelo_190_and_boe
    ff_service = FirefoxFilingService()

    # 1. Iniciar sesión asistida en Firefox
    session = await ff_service.start_session(
        model_code="190",
        fiscal_year=2026,
        period="0A",
        boe_content=boe_result.content_raw,
        use_sandbox=True,
        browser_type="firefox"
    )

    assert session.browser_type == "firefox"
    assert session.model_code == "190"
    assert session.session_id.startswith("ff-filing-")

    # 2. Ejecutar flujo de validación telemática
    updated_session = await ff_service.execute_assisted_workflow(session.session_id, boe_result.content_raw)

    assert updated_session.status == FilingSessionStatus.AWAITING_USER_SIGNATURE
    assert updated_session.preview_url is not None
    assert any("previsualización" in msg.lower() or "firma" in msg.lower() for msg in updated_session.validation_messages)


@pytest.mark.asyncio
async def test_qa_modelo_190_prohibits_chrome(sample_modelo_190_and_boe):
    """Verifica la prohibición constitucional de usar Chrome en la presentación del Modelo 190."""
    _, _, boe_result = sample_modelo_190_and_boe
    ff_service = FirefoxFilingService()

    with pytest.raises(FirefoxFilingError) as exc_info:
        await ff_service.start_session(
            model_code="190",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chrome"
        )

    assert "Google Chrome está estrictamente prohibido" in str(exc_info.value)

    with pytest.raises(FirefoxFilingError):
        await ff_service.start_session(
            model_code="190",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chromium"
        )


@pytest.mark.asyncio
async def test_qa_modelo_190_detects_corrupted_boe_file():
    """Verifica que un fichero del Modelo 190 corrupto o no estructurado sea detenido en VALIDATED_ERRORS."""
    ff_service = FirefoxFilingService()
    corrupted_boe = "MODELO190_CORRUPTO_LINEA_CORTA"

    session = await ff_service.start_session(
        model_code="190",
        fiscal_year=2026,
        period="0A",
        boe_content=corrupted_boe,
        use_sandbox=True,
        browser_type="firefox"
    )

    updated_session = await ff_service.execute_assisted_workflow(session.session_id, corrupted_boe)

    assert updated_session.status == FilingSessionStatus.VALIDATED_ERRORS
    assert any("error" in msg.lower() for msg in updated_session.validation_messages)
