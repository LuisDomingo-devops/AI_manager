"""
AuthService — Emisión y validación de tokens JWT para el usuario único.

Access token:  8 horas  (para uso en sesión de trabajo).
Refresh token: 30 días  (para renovar el access token sin volver a hacer login).

El secret se genera y persiste en data/.auth_secret si no está en el .env.
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from jose import JWTError, jwt

from app.adapters.memory.memory import _get_connection
from app.domain.services.user_service import AppUser, UserService

# ── Configuración del secret ──────────────────────────────────────────────────
_SECRET_FILE = Path(__file__).resolve().parents[3] / "data" / ".auth_secret"

def _load_or_create_secret() -> str:
    env_secret = os.getenv("AUTH_SECRET_KEY", "")
    if env_secret and len(env_secret) >= 32:
        return env_secret
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text(encoding="utf-8").strip()
    _SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_hex(32)
    _SECRET_FILE.write_text(new_secret, encoding="utf-8")
    return new_secret

_JWT_SECRET = _load_or_create_secret()
_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_HOURS = 8
_REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthService:
    # ── Login ─────────────────────────────────────────────────────────────
    @classmethod
    def login(cls, username: str, password: str) -> dict:
        """
        Autentica al usuario y devuelve access_token + refresh_token.
        Lanza ValueError si las credenciales son incorrectas.
        """
        user = UserService.authenticate(username, password)
        if not user:
            raise ValueError("Credenciales incorrectas o usuario inactivo.")

        access_token = cls._create_access_token(user)
        refresh_token, refresh_hash = cls._create_refresh_token()
        cls._store_refresh_token(refresh_hash)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": _ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        }

    # ── Refresh ───────────────────────────────────────────────────────────
    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> dict:
        """
        Valida el refresh token y emite un nuevo access token.
        Lanza ValueError si el refresh token es inválido, expirado o revocado.
        """
        token_hash = cls._hash_token(refresh_token)
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT expires_at, revoked FROM refresh_tokens WHERE token_hash = ?",
                (token_hash,)
            ).fetchone()

        if not row:
            raise ValueError("Refresh token no encontrado.")
        if row["revoked"]:
            raise ValueError("Refresh token ya fue revocado.")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now():
            raise ValueError("Refresh token expirado. Inicia sesión de nuevo.")

        user = UserService.get_user()
        if not user:
            raise ValueError("No se encontró el usuario de la licencia.")

        access_token = cls._create_access_token(user)
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": _ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        }

    # ── Logout ────────────────────────────────────────────────────────────
    @classmethod
    def logout(cls, refresh_token: str) -> bool:
        """Revoca el refresh token. Devuelve True si existía y fue revocado."""
        token_hash = cls._hash_token(refresh_token)
        with _get_connection() as conn:
            cursor = conn.execute(
                "UPDATE refresh_tokens SET revoked = 1 WHERE token_hash = ?",
                (token_hash,)
            )
            conn.commit()
        return cursor.rowcount > 0

    # ── Decode ────────────────────────────────────────────────────────────
    @classmethod
    def decode_access_token(cls, token: str) -> dict:
        """
        Decodifica y valida el access token JWT.
        Lanza ValueError si es inválido o ha expirado.
        """
        try:
            payload = jwt.decode(token, _JWT_SECRET, algorithms=[_ALGORITHM])
            return payload
        except JWTError as exc:
            raise ValueError(f"Token JWT inválido o expirado: {exc}") from exc

    # ── Helpers privados ──────────────────────────────────────────────────
    @classmethod
    def _create_access_token(cls, user: AppUser) -> str:
        expire = datetime.utcnow() + timedelta(hours=_ACCESS_TOKEN_EXPIRE_HOURS)
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "exp": expire,
            "type": "access",
        }
        return jwt.encode(payload, _JWT_SECRET, algorithm=_ALGORITHM)

    @classmethod
    def _create_refresh_token(cls) -> tuple[str, str]:
        """Devuelve (raw_token, token_hash)."""
        raw = secrets.token_hex(32)
        return raw, cls._hash_token(raw)

    @classmethod
    def _hash_token(cls, raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    @classmethod
    def _store_refresh_token(cls, token_hash: str) -> None:
        expires_at = (datetime.now() + timedelta(days=_REFRESH_TOKEN_EXPIRE_DAYS)).isoformat()
        with _get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO refresh_tokens (token_hash, expires_at, revoked) VALUES (?, ?, 0)",
                (token_hash, expires_at)
            )
            conn.commit()
