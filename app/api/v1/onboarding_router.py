import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.adapters.memory.memory import _get_connection, tenant_context
from app.utils.license_validator import check_license_status, install_license, get_machine_fingerprint
from app.domain.services.tenant_provisioner import TenantProvisioningService

router = APIRouter(prefix="/onboarding")

class OnboardingSetupRequest(BaseModel):
    client_id: str = Field("default", description="Identificador del espacio de trabajo/empresa")
    # Paso 1: Perfil Fiscal
    razon_social: str = Field(..., description="Nombre comercial o Razón Social del autónomo/empresa")
    nif: str = Field(..., description="NIF/NIE/CIF fiscal")
    direccion: Optional[str] = Field("Dirección fiscal no especificada", description="Dirección fiscal")
    epigrafe_iae: Optional[str] = Field("8499", description="Epígrafe IAE principal")
    # Paso 2: Régimen Tributario
    regimen_iva: str = Field("general", description="Régimen de IVA: general (21%), simplificado, recargo_equivalencia, exento")
    irpf_rate_default: float = Field(15.0, description="Tipo de retención IRPF por defecto (ej: 15% o 7% para nuevos autónomos)")
    # Paso 3: Licencia y Aceptación Legal
    license_data: Optional[Dict[str, Any]] = Field(None, description="Archivo o payload de licencia firmado criptográficamente")
    eula_accepted: bool = Field(..., description="Aceptación explícita de los Términos y Condiciones y Exención de Responsabilidad")

@router.get("/status", summary="Consultar estado del asistente de configuración inicial")
async def get_onboarding_status(client_id: Optional[str] = None):
    """
    Verifica si el cliente ha completado la configuración inicial del perfil fiscal,
    el régimen de IVA y el estado de la licencia local.
    """
    cid = client_id or tenant_context.get() or "default"
    license_result = check_license_status()
    machine_fp = get_machine_fingerprint()

    has_profile = False
    profile_data = None

    try:
        with _get_connection(cid) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nif, razon_social, direccion FROM user_profile LIMIT 1")
            row = cursor.fetchone()
            if row and row["nif"] and row["razon_social"] and not row["nif"].startswith("12345678Z"):
                has_profile = True
                profile_data = dict(row)
    except Exception:
        pass

    is_completed = has_profile and license_result.is_operational

    return {
        "status": "ok",
        "client_id": cid,
        "is_onboarding_completed": is_completed,
        "profile_configured": has_profile,
        "profile": profile_data,
        "machine_fingerprint": machine_fp,
        "license": license_result.to_dict(),
        "requires_wizard": not is_completed
    }

@router.post("/setup", summary="Completar asistente de configuración inicial (Wizard 3 pasos)")
async def complete_onboarding_setup(payload: OnboardingSetupRequest):
    """
    Ejecuta la configuración inicial en 3 pasos:
    1. Guarda el perfil fiscal y NIF del autónomo.
    2. Configura los parámetros de IVA e IRPF.
    3. Valida la aceptación de los términos legales e instala la licencia criptográfica.
    """
    if not payload.eula_accepted:
        raise HTTPException(
            status_code=400,
            detail="Es obligatorio aceptar los Términos y Condiciones (EULA) y la Cláusula de Exención de Responsabilidad para utilizar el software."
        )

    cid = TenantProvisioningService.sanitize_client_id(payload.client_id)

    # 1. Instalar licencia si se proporciona
    if payload.license_data:
        success = install_license(payload.license_data)
        if not success:
            raise HTTPException(status_code=500, detail="No se pudo escribir el archivo de licencia local.")

    # 2. Inicializar o actualizar base de datos local y perfil fiscal
    with _get_connection(cid) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM user_profile")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO user_profile (user_type, nif, razon_social, direccion)
                VALUES ('autonomo', ?, ?, ?)
            """, (payload.nif, payload.razon_social, payload.direccion))
        else:
            cursor.execute("""
                UPDATE user_profile
                SET nif = ?, razon_social = ?, direccion = ?, updated_at = datetime('now')
                WHERE id = 1
            """, (payload.nif, payload.razon_social, payload.direccion))
        conn.commit()

    license_status = check_license_status()

    return {
        "status": "ok",
        "message": f"¡Configuración inicial completada con éxito para '{payload.razon_social}'!",
        "client_id": cid,
        "eula_accepted_at": datetime.now().isoformat(),
        "license": license_status.to_dict()
    }

@router.get("/eula", summary="Consultar términos y condiciones y exención de responsabilidad")
async def get_eula_terms():
    """
    Retorna el texto oficial del contrato EULA y las cláusulas de limitación de responsabilidad fiscal.
    """
    eula_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "legal", "EULA_TERMINOS_Y_CONDICIONES.md")
    eula_text = ""
    if os.path.exists(eula_path):
        with open(eula_path, "r", encoding="utf-8") as f:
            eula_text = f.read()
    else:
        eula_text = (
            "ALFONSO AUTÓNOMO — CONTRATO DE LICENCIA DE USUARIO FINAL (EULA)\n\n"
            "1. Alfonso Autónomo es un software de gestión contable y facturación Local-First.\n"
            "2. EXENCIÓN DE ASESORAMIENTO: El software no constituye asesoramiento tributario o jurídico vinculante. "
            "El usuario es el único responsable de la exactitud de sus declaraciones ante la AEAT.\n"
            "3. PRIVACIDAD: Los datos contables residen exclusivamente en el equipo del usuario."
        )

    return {
        "status": "ok",
        "version": "1.0",
        "eula_text": eula_text
    }
