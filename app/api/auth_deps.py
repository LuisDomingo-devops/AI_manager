"""
auth_deps.py — Dependencia FastAPI para autenticación JWT.

Extrae y valida el Bearer token del header Authorization.
Compatible con el sistema verify_api_key existente (no lo reemplaza).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.services.auth_service import AuthService
from app.domain.services.user_service import AppUser, UserService

_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AppUser:
    """
    Dependencia FastAPI: valida el JWT Bearer token y devuelve el AppUser.

    Uso:
        @router.get("/me")
        async def me(user: AppUser = Depends(get_current_user)):
            ...
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de autenticación requerido.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = AuthService.decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = UserService.get_user()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )

    return user


# Alias conveniente para los routers
CurrentUser = Depends(get_current_user)
