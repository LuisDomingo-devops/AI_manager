"""
auth_router.py — Endpoints de autenticación para el usuario único por licencia.

Endpoints:
  POST /auth/setup    — Crea el usuario inicial (solo si no existe). Protegido por API Key.
  POST /auth/login    — Login con username + password → JWT.
  POST /auth/logout   — Revoca el refresh token.
  POST /auth/refresh  — Renueva el access token con un refresh token válido.
  GET  /auth/me       — Perfil del usuario autenticado.
  PATCH /auth/password — Cambiar contraseña (requiere la antigua).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.api.auth_deps import get_current_user
from app.api.routes import verify_api_key
from app.domain.services.auth_service import AuthService
from app.domain.services.user_service import AppUser, UserService
from app.utils.license_validator import check_license_status

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class SetupRequest(BaseModel):
    username: str = Field(..., min_length=3, description="Nombre de usuario (mín. 3 caracteres)")
    password: str = Field(..., min_length=8, description="Contraseña (mín. 8 caracteres)")
    email: Optional[str] = Field(None, description="Email de contacto (opcional)")


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., description="Contraseña actual")
    new_password: str = Field(..., min_length=8, description="Contraseña nueva (mín. 8 caracteres)")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/setup",
    status_code=status.HTTP_201_CREATED,
    summary="Crear el usuario inicial de la licencia",
    description="Crea el usuario único asociado a esta licencia. Solo puede llamarse una vez. Requiere API Key.",
    dependencies=[Depends(verify_api_key)],
)
async def setup_user(payload: SetupRequest):
    """
    Crea el primer y único usuario de la instalación.
    Si ya existe un usuario, devuelve 409 Conflict.
    """
    try:
        user_id = UserService.setup_user(
            username=payload.username,
            password=payload.password,
            email=payload.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    license_info = check_license_status()
    return {
        "status": "created",
        "user_id": user_id,
        "username": payload.username.strip().lower(),
        "license_tier": license_info.tier or license_info.license_type,
        "message": "Usuario creado correctamente. Usa /auth/login para iniciar sesión.",
    }


@router.post(
    "/login",
    summary="Iniciar sesión y obtener JWT",
)
async def login(payload: LoginRequest):
    """
    Autentica al usuario con username + password.
    Devuelve un access_token (8h) y un refresh_token (30 días).
    """
    try:
        tokens = AuthService.login(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    license_info = check_license_status()
    return {
        **tokens,
        "license_tier": license_info.tier or license_info.license_type,
        "license_status": license_info.status,
    }


@router.post(
    "/refresh",
    summary="Renovar access token con refresh token",
)
async def refresh_token(payload: RefreshRequest):
    """
    Emite un nuevo access token a partir de un refresh token válido.
    No requiere reintroducir contraseña.
    """
    try:
        return AuthService.refresh_access_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post(
    "/logout",
    summary="Cerrar sesión y revocar refresh token",
)
async def logout(payload: LogoutRequest):
    """
    Revoca el refresh token indicado. El access token expirará de forma natural (8h).
    """
    revoked = AuthService.logout(payload.refresh_token)
    return {
        "status": "ok" if revoked else "not_found",
        "message": "Sesión cerrada." if revoked else "El token no se encontró o ya estaba revocado.",
    }


@router.get(
    "/me",
    summary="Perfil del usuario autenticado",
)
async def get_me(user: AppUser = Depends(get_current_user)):
    """
    Devuelve los datos del usuario autenticado y el estado de su licencia.
    Requiere Bearer token válido.
    """
    license_info = check_license_status()
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "license": {
            "tier": license_info.tier or license_info.license_type,
            "status": license_info.status,
            "holder": license_info.holder,
            "expires_at": license_info.expires_at,
            "days_until_expiration": license_info.days_until_expiration,
            "is_operational": license_info.is_operational,
        },
    }


@router.patch(
    "/password",
    summary="Cambiar contraseña",
)
async def change_password(
    payload: ChangePasswordRequest,
    user: AppUser = Depends(get_current_user),
):
    """
    Cambia la contraseña del usuario autenticado.
    Requiere la contraseña actual como verificación.
    """
    try:
        success = UserService.change_password(payload.old_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La contraseña actual no es correcta.",
        )

    return {"status": "ok", "message": "Contraseña actualizada correctamente."}
