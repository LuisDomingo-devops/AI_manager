"""
Tests de integración — Feature gating por licencia.
Verifica que el mapa de features refleja correctamente los tiers.
"""
import pytest
from unittest.mock import patch

from app.infrastructure.security.license_features import require_feature
from app.utils.license_validator import (
    LicenseStatusResult,
    TIER_CAPABILITIES,
    BASIC_ALLOWED_TOOLS,
)


# ── Verifactu disponible en todos los tiers ───────────────────────────────────

def test_verifactu_disponible_en_basic():
    """create_invoice (verifactu) está en BASIC_ALLOWED_TOOLS."""
    assert "create_invoice" in BASIC_ALLOWED_TOOLS


def test_verifactu_disponible_en_pro():
    """create_invoice está en el tier pro."""
    pro_tools = TIER_CAPABILITIES["pro"]["allowed_tools"]
    assert "create_invoice" in pro_tools


def test_verifactu_disponible_en_advisor():
    """create_invoice está en el tier advisor."""
    advisor_tools = TIER_CAPABILITIES["advisor"]["allowed_tools"]
    assert "create_invoice" in advisor_tools


# ── Features exclusivos de tiers superiores ───────────────────────────────────

def test_open_banking_no_disponible_en_basic():
    """run_bank_reconciliation NO está en BASIC_ALLOWED_TOOLS."""
    assert "run_bank_reconciliation" not in BASIC_ALLOWED_TOOLS


def test_open_banking_disponible_en_pro():
    """run_bank_reconciliation sí está en el tier pro."""
    pro_tools = TIER_CAPABILITIES["pro"]["allowed_tools"]
    assert "run_bank_reconciliation" in pro_tools


def test_einvoice_b2b_no_disponible_en_pro():
    """export_einvoice_tool NO está en el tier pro."""
    pro_tools = TIER_CAPABILITIES["pro"]["allowed_tools"]
    advisor_tools = TIER_CAPABILITIES["advisor"]["allowed_tools"]
    assert "export_einvoice_tool" not in pro_tools
    assert "export_einvoice_tool" in advisor_tools


# ── require_feature como dependencia FastAPI ─────────────────────────────────

def test_require_feature_no_lanza_excepcion_para_feature_disponible():
    """
    La función interna de require_feature no lanza HTTPException
    cuando el feature está disponible en el tier activo.
    """
    mock_license = LicenseStatusResult(
        status="active",
        is_operational=True,
        tier="advisor",
        license_type="advisor"
    )
    with patch("app.infrastructure.security.license_features.check_license_status", return_value=mock_license), \
         patch("app.infrastructure.security.license_features.get_active_license_tier", return_value="advisor"):
        # No debe lanzar excepción
        dep = require_feature("banking")
        # dep es un Depends object; la función interna es callable
        # Invocamos la función interna directamente
        inner_fn = dep.dependency
        inner_fn()  # No debe lanzar


def test_require_feature_lanza_excepcion_para_feature_no_disponible():
    """
    require_feature lanza HTTPException 403 cuando el feature
    no está disponible en el tier activo.
    """
    from fastapi import HTTPException
    with patch("app.infrastructure.security.license_features.get_active_license_tier", return_value="basic"):
        dep = require_feature("banking")
        inner_fn = dep.dependency
        with pytest.raises(HTTPException) as exc_info:
            inner_fn()
        assert exc_info.value.status_code == 403


def test_require_feature_lanza_402_sin_licencia():
    """
    Sin licencia operativa, require_feature lanza 402 Payment Required.
    """
    from fastapi import HTTPException
    with patch("app.infrastructure.security.license_features.get_active_license_tier", return_value="none"):
        dep = require_feature("billing")
        inner_fn = dep.dependency
        with pytest.raises(HTTPException) as exc_info:
            inner_fn()
        assert exc_info.value.status_code == 402


def test_verifactu_no_bloqueado_en_basic():
    """
    require_feature('verifactu') NO lanza excepción con tier basic,
    porque Verifactu está disponible para todos los tiers.
    """
    with patch("app.infrastructure.security.license_features.get_active_license_tier", return_value="basic"):
        dep = require_feature("verifactu")
        inner_fn = dep.dependency
        # No debe lanzar excepción
        inner_fn()
