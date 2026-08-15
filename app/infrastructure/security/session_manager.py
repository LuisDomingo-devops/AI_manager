import secrets
import hashlib
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Optional
from app.adapters.memory.memory import _get_connection, tenant_context
from app.utils.logger import app_logger

class SessionManager:
    _lock = threading.Lock()
    _db_initialized = False

    @classmethod
    def init_session_schema(cls) -> None:
        """Inicializa la tabla de sesiones activas."""
        if cls._db_initialized:
            return
        with cls._lock:
            if cls._db_initialized:
                return
            conn = _get_connection()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        token_hash    TEXT PRIMARY KEY,
                        client_id     TEXT NOT NULL,
                        created_at    TEXT NOT NULL,
                        expires_at    TEXT NOT NULL,
                        revoked       INTEGER NOT NULL DEFAULT 0
                    )
                """)
                conn.commit()
                cls._db_initialized = True
            finally:
                conn.close()

    @classmethod
    def create_session(cls, client_id: str, duration_hours: float = 2.0) -> str:
        """Crea una sesión nueva para un tenant y devuelve el token crudo."""
        cls.init_session_schema()
        raw_token = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        
        now = datetime.now()
        expires = now + timedelta(hours=duration_hours)
        
        conn = _get_connection()
        try:
            conn.execute("""
                INSERT INTO user_sessions (token_hash, client_id, created_at, expires_at, revoked)
                VALUES (?, ?, ?, ?, 0)
            """, (token_hash, client_id.strip().lower(), now.isoformat(), expires.isoformat()))
            conn.commit()
        finally:
            conn.close()
            
        app_logger.info(f"Sesión creada para tenant '{client_id}', expira a las {expires.isoformat()}")
        return raw_token

    @classmethod
    def validate_session_token(cls, token: str) -> Optional[str]:
        """Valida el token provisto. Si es válido devuelve el client_id y establece el tenant_context."""
        cls.init_session_schema()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        
        conn = _get_connection()
        try:
            row = conn.execute(
                "SELECT client_id, expires_at, revoked FROM user_sessions WHERE token_hash = ?",
                (token_hash,)
            ).fetchone()
        finally:
            conn.close()
            
        if not row:
            return None
            
        client_id = row["client_id"]
        expires_at = datetime.fromisoformat(row["expires_at"])
        revoked = row["revoked"]
        
        if revoked == 1:
            app_logger.warning(f"Intento de usar token revocado para tenant '{client_id}'")
            return None
            
        if datetime.now() > expires_at:
            app_logger.warning(f"Sesión expirada para tenant '{client_id}'")
            return None
            
        # Establecer contexto
        tenant_context.set(client_id)
        return client_id

    @classmethod
    def revoke_session_token(cls, token: str) -> bool:
        """Revoca de forma inmediata un token de sesión."""
        cls.init_session_schema()
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        
        conn = _get_connection()
        try:
            cursor = conn.execute(
                "UPDATE user_sessions SET revoked = 1 WHERE token_hash = ?",
                (token_hash,)
            )
            conn.commit()
            success = cursor.rowcount > 0
        finally:
            conn.close()
            
        if success:
            app_logger.info("Token de sesión revocado exitosamente.")
        return success
