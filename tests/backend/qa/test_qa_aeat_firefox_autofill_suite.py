"""
test_qa_aeat_firefox_autofill_suite.py
======================================
Suite de QA con Playwright / sandbox para la automatización asistida en Mozilla Firefox.
Valida:
1. Lanzamiento de navegador exclusivo Firefox (sin invocar Chrome).
2. Importación y precarga del fichero telemático oficial BOE (.ses).
3. Simulación de validación en la Sede Electrónica de la AEAT.
4. Transición y parada estricta en el estado AWAITING_USER_SIGNATURE (Human-in-the-Loop).
5. Detección de errores y transición a VALIDATED_ERRORS cuando hay inconsistencias bloqueantes.
"""

import pytest
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.models.billing import FilingSessionStatus, FirefoxFilingSessionDTO


@pytest.mark.asyncio
async def test_qa_assisted_filing_flow_reaches_awaiting_signature():
    """Valida el ciclo de vida completo de la sesión asistida culminando en parada para firma manual."""
    service = FirefoxFilingService()
    boe_sample = (
        "130320261T12345678ZEMPRESA DE PRUEBA SL                      912345678            \r\n"
        "230320261T12345678Z0000000000010000000000000000021000000000000021000\r\n"
    )

    session = await service.start_session(
        model_code="303",
        fiscal_year=2026,
        period="1T",
        boe_content=boe_sample,
        use_sandbox=True,
        browser_type="firefox"
    )

    assert session.session_id.startswith("ff-filing-")
    assert session.browser_type == "firefox"
    assert session.status in [FilingSessionStatus.INITIALIZED, FilingSessionStatus.AWAITING_USER_SIGNATURE]

    # Ejecutar simulación de importación y validación
    updated_session = await service.execute_assisted_workflow(session.session_id, boe_sample)

    assert updated_session.status == FilingSessionStatus.AWAITING_USER_SIGNATURE
    assert any("previsualización" in msg.lower() or "firma" in msg.lower() for msg in updated_session.validation_messages)
    assert updated_session.preview_url is not None


@pytest.mark.asyncio
async def test_qa_assisted_filing_detects_blocking_errors():
    """Valida que si el fichero telemático tiene un error estructural, la sesión pasa a VALIDATED_ERRORS."""
    service = FirefoxFilingService()
    # Fichero corrupto o sin datos mínimos
    invalid_boe = "CONTENIDO_INVALIDO_SIN_FORMATO"

    session = await service.start_session(
        model_code="303",
        fiscal_year=2026,
        period="1T",
        boe_content=invalid_boe,
        use_sandbox=True,
        browser_type="firefox"
    )

    updated_session = await service.execute_assisted_workflow(session.session_id, invalid_boe)

    assert updated_session.status == FilingSessionStatus.VALIDATED_ERRORS
    assert len(updated_session.validation_messages) > 0
    assert any("error" in msg.lower() for msg in updated_session.validation_messages)
