"""
UserService — Gestión del usuario único por licencia.

Reglas:
  - Solo puede existir UN usuario (1 licencia = 1 usuario).
  - Las contraseñas nunca se almacenan en claro, solo el hash bcrypt.
  - setup_user() falla si ya existe un usuario registrado.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from passlib.context import CryptContext

from app.adapters.memory.memory import _get_connection

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class AppUser:
    id: int
    username: str
    email: Optional[str]
    is_active: bool
    created_at: str
    last_login_at: Optional[str]


class UserService:
    # ── Schema fallback ────────────────────────────────────────────────────
    @classmethod
    def _ensure_schema(cls) -> None:
        """Crea las tablas si la migración 014 aún no se ha aplicado."""
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_user (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    username      TEXT NOT NULL UNIQUE,
                    email         TEXT,
                    password_hash TEXT NOT NULL,
                    is_active     INTEGER NOT NULL DEFAULT 1,
                    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
                    last_login_at TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS refresh_tokens (
                    token_hash  TEXT PRIMARY KEY,
                    expires_at  TEXT NOT NULL,
                    revoked     INTEGER NOT NULL DEFAULT 0,
                    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

    # ── Creación ──────────────────────────────────────────────────────────
    @classmethod
    def user_exists(cls) -> bool:
        """Comprueba si ya hay un usuario registrado."""
        cls._ensure_schema()
        with _get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM app_user").fetchone()
            return row[0] > 0

    @classmethod
    def setup_user(cls, username: str, password: str, email: Optional[str] = None) -> int:
        """
        Crea el usuario único de la licencia.
        Lanza ValueError si ya existe un usuario (1 licencia = 1 usuario).
        """
        cls._ensure_schema()
        if cls.user_exists():
            raise ValueError(
                "Ya existe un usuario registrado para esta licencia. "
                "Solo se permite un usuario por licencia."
            )
        if not username or len(username.strip()) < 3:
            raise ValueError("El nombre de usuario debe tener al menos 3 caracteres.")
        if not password or len(password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")

        password_hash = _pwd_ctx.hash(password.strip())
        with _get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO app_user (username, email, password_hash) VALUES (?, ?, ?)",
                (username.strip().lower(), email, password_hash)
            )
            conn.commit()
            return cursor.lastrowid

    # ── Autenticación ─────────────────────────────────────────────────────
    @classmethod
    def authenticate(cls, username: str, password: str) -> Optional[AppUser]:
        """
        Verifica las credenciales. Devuelve AppUser si son correctas, None si no.
        Actualiza last_login_at en caso de éxito.
        """
        cls._ensure_schema()
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, email, password_hash, is_active, created_at, last_login_at "
                "FROM app_user WHERE username = ?",
                (username.strip().lower(),)
            ).fetchone()

        if not row:
            return None
        if not row["is_active"]:
            return None
        if not _pwd_ctx.verify(password, row["password_hash"]):
            return None

        # Actualizar last_login_at
        with _get_connection() as conn:
            conn.execute(
                "UPDATE app_user SET last_login_at = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()

        return AppUser(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )

    # ── Consulta ──────────────────────────────────────────────────────────
    @classmethod
    def get_user(cls) -> Optional[AppUser]:
        """Devuelve el único usuario registrado, o None si no existe."""
        cls._ensure_schema()
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT id, username, email, is_active, created_at, last_login_at FROM app_user LIMIT 1"
            ).fetchone()
        if not row:
            return None
        return AppUser(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
            last_login_at=row["last_login_at"],
        )

    # ── Cambio de contraseña ──────────────────────────────────────────────
    @classmethod
    def change_password(cls, old_password: str, new_password: str) -> bool:
        """
        Cambia la contraseña verificando la antigua primero.
        Devuelve True si el cambio fue exitoso.
        """
        cls._ensure_schema()
        if not new_password or len(new_password) < 8:
            raise ValueError("La contraseña nueva debe tener al menos 8 caracteres.")

        with _get_connection() as conn:
            row = conn.execute(
                "SELECT id, password_hash FROM app_user LIMIT 1"
            ).fetchone()

        if not row:
            return False
        if not _pwd_ctx.verify(old_password, row["password_hash"]):
            return False

        new_hash = _pwd_ctx.hash(new_password)
        with _get_connection() as conn:
            conn.execute(
                "UPDATE app_user SET password_hash = ? WHERE id = ?",
                (new_hash, row["id"])
            )
            conn.commit()
        return True
