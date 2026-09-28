"""
Test de integración de resiliencia en configuración y onboarding (config.py y onboarding_router.py).
Valida que la recarga de roles y la consulta de estado de onboarding gestionen excepciones
de base de datos y parsing sin imports tardíos de error_logger.
"""

import asyncio
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from app.config import settings
from app.api.v1.onboarding_router import get_onboarding_status

def test_config_and_onboarding_no_inline_error_logger_imports():
    """Verifica que config.py y onboarding_router.py no contengan imports tardíos de error_logger."""
    cfg_source = (Path(__file__).resolve().parents[3] / "app" / "config.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in cfg_source, (
        "config.py aún contiene imports inline tardíos de error_logger"
    )
    onb_source = (Path(__file__).resolve().parents[3] / "app" / "api" / "v1" / "onboarding_router.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in onb_source, (
        "onboarding_router.py aún contiene imports inline tardíos de error_logger"
    )

def test_config_get_client_role_dotenv_resilience(monkeypatch):
    """Verifica que get_client_role tolere errores al recargar dotenv."""
    monkeypatch.setattr("sys.modules", {}) # Forzar flujo no-test de recarga
    with patch("dotenv.load_dotenv", side_effect=OSError("Permission denied on .env")):
        role = settings.get_client_role("client_test")
        assert role is not None

def test_onboarding_status_db_error_resilience():
    """Verifica que get_onboarding_status tolere errores de base de datos devolviendo respuesta segura."""
    with patch("app.api.v1.onboarding_router._get_connection", side_effect=Exception("DB connection dropped")):
        resp = asyncio.run(get_onboarding_status("client_fallback"))
        assert resp["status"] == "ok"
        assert resp["profile_configured"] is False
