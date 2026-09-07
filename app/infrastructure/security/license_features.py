"""
license_features.py — Feature gating por tier de licencia.

Verifactu está disponible en TODOS los tiers (básico, pro, advisor).
El mapa se construye sobre TIER_CAPABILITIES del sistema de licencias existente.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status

from app.utils.license_validator import (
    TIER_CAPABILITIES,
    check_license_status,
    get_active_license_tier,
)


def get_license_tier() -> str:
    """Devuelve el tier activo de la licencia, o 'none' si no hay licencia válida."""
    return get_active_license_tier()


def require_feature(feature: str):
    """
    Dependencia FastAPI que bloquea el endpoint si el feature no está
    disponible en la licencia activa.

    Uso:
        @router.post("/endpoint", dependencies=[Depends(require_feature("payroll"))])

    Features disponibles en cada tier:
        basic:   billing, accounting, verifactu, contacts (todos los básicos)
        pro:     basic + banking, payroll, quotes, export, cash_flow
        advisor: pro + einvoice_b2b, multi_tenant
    """
    def _check():
        tier = get_active_license_tier()
        if tier == "none":
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="Licencia no operativa. Activa o renueva tu suscripción."
            )

        # Mapeamos los features de API a tool names del sistema existente
        FEATURE_TOOL_MAP: dict[str, str] = {
            "billing":        "create_invoice",
            "accounting":     "get_libro_diario",
            "verifactu":      "create_invoice",    # siempre incluido en basic
            "contacts":       "get_clients",
            "banking":        "run_bank_reconciliation",
            "payroll":        "create_invoice",    # payroll tools se controlan por tier_capabilities
            "quotes":         "create_quote",
            "export":         "export_advisor_pack",
            "cash_flow":      "get_cash_flow_forecast_tool",
            "einvoice_b2b":   "export_einvoice_tool",
            "multi_tenant":   "get_projects_wip",
            "ai_advisor":     "send_to_advisor",
        }

        tool_name = FEATURE_TOOL_MAP.get(feature)
        if not tool_name:
            # Feature desconocido: denegamos por seguridad
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' no reconocido."
            )

        tier_info = TIER_CAPABILITIES.get(tier, TIER_CAPABILITIES["basic"])
        allowed_tools = tier_info.get("allowed_tools", set())

        if tool_name not in allowed_tools:
            upgrade_msg = tier_info.get("upgrade_message", "Actualiza tu plan para acceder a esta funcionalidad.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Feature '{feature}' no incluido en tu licencia '{tier_info.get('name')}'. {upgrade_msg}"
            )

    return Depends(_check)
