"""
Suite de QA para la validación y automatización asistida del Modelo 180 en Mozilla Firefox.
Verifica:
1. Generación de exportación telemática oficial BOE del Modelo 180 e integración con FirefoxFilingService.
2. Uso exclusivo del navegador Mozilla Firefox y prohibición estricta de Google Chrome.
3. Parada del flujo asistido en estado AWAITING_USER_SIGNATURE (Human-in-the-Loop) para firma manual.
4. Rechazo e interrupción ante ficheros BOE corruptos o no conformes.
"""

import pytest
from app.domain.models.billing import (
    Model180ResultDTO,
    Model180PerceptorDTO,
    InmuebleArrendadoDTO,
    DeclarantInfoDTO,
    FilingSessionStatus
)
from app.domain.services.boe_export_service import BoeExportService
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.exceptions import FirefoxFilingError


@pytest.fixture
def sample_modelo_180_and_boe():
    inmueble = InmuebleArrendadoDTO(
        situacion_inmueble=1,
        referencia_catastral="9872023VH5797S0001WX",
        tipo_via="CL",
        nombre_via="GRAN VIA",
        numero="28",
        municipio="MADRID",
        codigo_postal="28013",
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
    model_180 = Model180ResultDTO(
        fiscal_year=2026,
        total_perceptores=1,
        total_base_retenciones=10000.0,
        total_retenciones_practicadas=1900.0,
        perceptores=[perceptor]
    )
    declarant = DeclarantInfoDTO(
        nif="B87654321",
        name="EMPRESA DECLARANTE SL",
        phone="912345678"
    )

    boe_service = BoeExportService()
    boe_result = boe_service.export_model_180_boe(model_180, declarant)
    return model_180, declarant, boe_result


@pytest.mark.asyncio
async def test_qa_modelo_180_firefox_workflow_success(sample_modelo_180_and_boe):
    """Verifica que el flujo asistido del Modelo 180 en Firefox alcanza la previsualización y espera de firma."""
    model_180, declarant, boe_result = sample_modelo_180_and_boe
    ff_service = FirefoxFilingService()

    # 1. Iniciar sesión asistida en Firefox
    session = await ff_service.start_session(
        model_code="180",
        fiscal_year=2026,
        period="0A",
        boe_content=boe_result.content_raw,
        use_sandbox=True,
        browser_type="firefox"
    )

    assert session.browser_type == "firefox"
    assert session.model_code == "180"
    assert session.session_id.startswith("ff-filing-")

    # 2. Ejecutar flujo de validación telemática en Firefox
    updated_session = await ff_service.execute_assisted_workflow(session.session_id, boe_result.content_raw)

    assert updated_session.status == FilingSessionStatus.AWAITING_USER_SIGNATURE
    assert updated_session.preview_url is not None
    assert any("previsualización" in msg.lower() or "firma" in msg.lower() for msg in updated_session.validation_messages)


@pytest.mark.asyncio
async def test_qa_modelo_180_prohibits_chrome(sample_modelo_180_and_boe):
    """Verifica la prohibición constitucional de usar Chrome en la presentación del Modelo 180."""
    _, _, boe_result = sample_modelo_180_and_boe
    ff_service = FirefoxFilingService()

    with pytest.raises(FirefoxFilingError) as exc_info:
        await ff_service.start_session(
            model_code="180",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chrome"
        )

    assert "Google Chrome está estrictamente prohibido" in str(exc_info.value)

    with pytest.raises(FirefoxFilingError):
        await ff_service.start_session(
            model_code="180",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chromium"
        )


@pytest.mark.asyncio
async def test_qa_modelo_180_detects_corrupted_boe_file():
    """Verifica que un fichero del Modelo 180 corrupto o no estructurado sea detenido en VALIDATED_ERRORS."""
    ff_service = FirefoxFilingService()
    corrupted_boe = "MODELO180_CORRUPTO_LINEA_CORTA"

    session = await ff_service.start_session(
        model_code="180",
        fiscal_year=2026,
        period="0A",
        boe_content=corrupted_boe,
        use_sandbox=True,
        browser_type="firefox"
    )

    updated_session = await ff_service.execute_assisted_workflow(session.session_id, corrupted_boe)

    assert updated_session.status == FilingSessionStatus.VALIDATED_ERRORS
    assert any("error" in msg.lower() for msg in updated_session.validation_messages)
