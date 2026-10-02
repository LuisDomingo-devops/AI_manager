"""
test_browser_policy_enforcement.py
==================================
Pruebas unitarias de imposición estricta de la política de navegación:
- Prohibición absoluta de Google Chrome / Chromium.
- Exigencia exclusiva de Mozilla Firefox.
- Verificación de excepciones y metadatos de auditoría ante intentos de transgresión.
"""
import pytest
from app.domain.services.firefox_filing_service import FirefoxFilingService
from app.domain.exceptions import FirefoxFilingError


def test_assert_firefox_only_allows_firefox():
    """Valida que Mozilla Firefox en distintas capitalizaciones es admitido."""
    FirefoxFilingService.assert_firefox_only("firefox")
    FirefoxFilingService.assert_firefox_only("Firefox")
    FirefoxFilingService.assert_firefox_only("FIREFOX ")


def test_assert_firefox_only_rejects_chrome_explicitly():
    """Valida que cualquier intento de invocar Chrome lanza FirefoxFilingError."""
    disallowed = [
        "chrome",
        "google-chrome",
        "chromium",
        "CHROME",
        "Google Chrome Canary",
        "msedge",
        "webkit"
    ]
    for browser in disallowed:
        with pytest.raises(FirefoxFilingError) as exc_info:
            FirefoxFilingService.assert_firefox_only(browser)
        err = exc_info.value
        assert "prohibido" in err.message.lower() or "no soportado" in err.message.lower()
        assert err.details.get("required_browser") == "firefox"


@pytest.mark.asyncio
async def test_start_session_fails_if_non_firefox_requested():
    """Valida que el servicio rechaza la creación de sesiones si no es Firefox."""
    service = FirefoxFilingService()
    with pytest.raises(FirefoxFilingError):
        await service.start_session(
            model_code="303",
            fiscal_year=2026,
            period="1T",
            boe_content="130320261T...",
            browser_type="chrome"
        )
