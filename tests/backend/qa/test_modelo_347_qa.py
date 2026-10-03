"""
Suite de QA para la validación y automatización asistida del Modelo 347 en Mozilla Firefox.
Verifica:
1. Generación de exportación telemática oficial BOE del Modelo 347 e integración con FirefoxFilingService.
2. Uso exclusivo del navegador Mozilla Firefox y prohibición estricta de Google Chrome.
3. Parada del flujo asistido en estado AWAITING_USER_SIGNATURE (Human-in-the-Loop) para firma manual.
4. Rechazo e interrupción ante ficheros BOE corruptos o no conformes.
"""

import pytest
from app.domain.models.billing import (
    Model347ResultDTO,
    Model347DeclaredDTO,
    DeclarantInfoDTO,
    FilingSessionStatus
)
from app.domain.services.boe_export_service import BoeExportService
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.exceptions import FirefoxFilingError


@pytest.fixture
def sample_modelo_347_and_boe():
    records = [
        Model347DeclaredDTO(
            nif="A11111111",
            name="PROVEEDOR PRINCIPAL SA",
            province_code="28",
            operation_key="A",
            total_annual_amount=7260.00,
            quarter_1_amount=1815.00,
            quarter_2_amount=1815.00,
            quarter_3_amount=1815.00,
            quarter_4_amount=1815.00
        ),
        Model347DeclaredDTO(
            nif="12345678Z",
            name="CLIENTE VIP ANTONIO",
            province_code="08",
            operation_key="B",
            total_annual_amount=9680.00,
            quarter_1_amount=6050.00,
            quarter_2_amount=3630.00,
            quarter_3_amount=0.00,
            quarter_4_amount=0.00,
            cash_amount=9680.00
        )
    ]
    model_347 = Model347ResultDTO(
        fiscal_year=2026,
        declarant_nif="B87654321",
        declarant_name="INNOVACIONES TECNOLOGICAS SL",
        total_declared_records=2,
        total_operations_amount=16940.00,
        total_cash_amount=9680.00,
        declared_records=records
    )
    declarant = DeclarantInfoDTO(
        nif="B87654321",
        name="INNOVACIONES TECNOLOGICAS SL",
        phone="912345678"
    )

    boe_service = BoeExportService()
    boe_result = boe_service.export_model_347_boe(model_347, declarant)
    return model_347, declarant, boe_result


@pytest.mark.asyncio
async def test_qa_modelo_347_firefox_workflow_success(sample_modelo_347_and_boe):
    """Verifica que el flujo asistido del Modelo 347 en Firefox alcanza la previsualización y espera de firma."""
    model_347, declarant, boe_result = sample_modelo_347_and_boe
    ff_service = FirefoxFilingService()

    # 1. Iniciar sesión asistida en Firefox
    session = await ff_service.start_session(
        model_code="347",
        fiscal_year=2026,
        period="0A",
        boe_content=boe_result.content_raw,
        use_sandbox=True,
        browser_type="firefox"
    )

    assert session.browser_type == "firefox"
    assert session.model_code == "347"
    assert session.session_id.startswith("ff-filing-")

    # 2. Ejecutar flujo de validación telemática en Firefox
    updated_session = await ff_service.execute_assisted_workflow(session.session_id, boe_result.content_raw)

    assert updated_session.status == FilingSessionStatus.AWAITING_USER_SIGNATURE
    assert updated_session.preview_url is not None
    assert any("previsualización" in msg.lower() or "firma" in msg.lower() for msg in updated_session.validation_messages)


@pytest.mark.asyncio
async def test_qa_modelo_347_prohibits_chrome(sample_modelo_347_and_boe):
    """Verifica la prohibición constitucional de usar Chrome en la presentación del Modelo 347."""
    _, _, boe_result = sample_modelo_347_and_boe
    ff_service = FirefoxFilingService()

    with pytest.raises(FirefoxFilingError) as exc_info:
        await ff_service.start_session(
            model_code="347",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chrome"
        )

    assert "Google Chrome está estrictamente prohibido" in str(exc_info.value)

    with pytest.raises(FirefoxFilingError):
        await ff_service.start_session(
            model_code="347",
            fiscal_year=2026,
            period="0A",
            boe_content=boe_result.content_raw,
            use_sandbox=True,
            browser_type="chromium"
        )


@pytest.mark.asyncio
async def test_qa_modelo_347_detects_corrupted_boe_file():
    """Verifica que un fichero del Modelo 347 corrupto o no estructurado sea detenido en VALIDATED_ERRORS."""
    ff_service = FirefoxFilingService()
    corrupted_boe = "MODELO347_CORRUPTO_LINEA_CORTA"

    session = await ff_service.start_session(
        model_code="347",
        fiscal_year=2026,
        period="0A",
        boe_content=corrupted_boe,
        use_sandbox=True,
        browser_type="firefox"
    )

    updated_session = await ff_service.execute_assisted_workflow(session.session_id, corrupted_boe)

    assert updated_session.status == FilingSessionStatus.VALIDATED_ERRORS
    assert any("error" in msg.lower() for msg in updated_session.validation_messages)
