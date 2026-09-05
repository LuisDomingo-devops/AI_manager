"""
MEMORY — Memoria de diálogo y almacenamiento de historial.

¿QUÉ HACE?
Mantiene el historial de la conversación actual por sesión en memoria volátil (RAM).

¿CUÁNDO LO HACE?
Durante el procesamiento de consultas para recuperar mensajes previos del usuario y el asistente e inyectarlos en el prompt.

¿CÓMO LO HACE?
Almacenando listas de mensajes estructurados en un diccionario indexado por `session_id` con hilos seguros.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/domain/planner_orchestrator.py (consulta el historial para contextualizar al modelo)
- app/api/routes.py (ofrece endpoints para leer, listar y borrar historiales por sesión)
"""

import json
import os
import sys
from collections import deque
from typing import Deque, Dict, List
from app.domain.ports.memory_port import MemoryPort
from app.infrastructure.database.connection_manager import (
    _get_connection, 
    IS_TESTING,
    DB_PATH,
    tenant_context,
    init_all_schemas as _init_db_schema
)


class SessionMemory(MemoryPort):
    """
    Gestiona el historial de conversación por sesión.

    - Persiste en SQLite para sobrevivir reinicios.
    - Mantiene una caché en RAM (deque) para lecturas rápidas.
    - Aplica un límite max_messages: solo se guardan los N mensajes más recientes.
    """

    def __init__(self, max_messages: int = 20, is_testing: bool | None = None):
        self.max_messages = max_messages
        # Caché en RAM: session_id:client_id → deque de dicts {role, content}
        self._cache: Dict[str, Deque[Dict[str, str]]] = {}
        self.is_testing = is_testing if is_testing is not None else IS_TESTING

    def _resolve_session_id(self, session_id: str) -> str:
        if not session_id:
            return session_id
        if self.is_testing:
            return session_id
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        return f"daily_{today_str}"

    # ------------------------------------------------------------------
    # Caché
    # ------------------------------------------------------------------

    def _ensure_loaded(self, session_id: str, client_id: str | None = None) -> None:
        """Carga el historial en memoria si no está ya en caché."""
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        if cache_key in self._cache:
            return

        with _get_connection(cid) as conn:
            rows = conn.execute(
                """
                SELECT role, content FROM messages
                WHERE session_id = ? AND client_id = ?
                ORDER BY id ASC
                """,
                (session_id, cid),
            ).fetchall()

        from app.utils.encryption import encryptor
        self._cache[cache_key] = deque(
            [{"role": r["role"], "content": encryptor.decrypt(r["content"])} for r in rows],
            maxlen=self.max_messages,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def add_message(self, session_id: str, role: str, content: str, client_id: str | None = None) -> None:
        if not session_id:
            return

        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._ensure_loaded(session_id, client_id)
        self._cache[cache_key].append({"role": role, "content": content})

        from app.utils.encryption import encryptor
        encrypted_content = encryptor.encrypt(content)

        with _get_connection(cid) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, client_id, role, content) VALUES (?, ?, ?, ?)",
                (session_id, cid, role, encrypted_content),
            )
            # Borrar mensajes viejos que superen el límite
            conn.execute(
                """
                DELETE FROM messages
                WHERE session_id = ? AND client_id = ?
                AND id NOT IN (
                    SELECT id FROM messages
                    WHERE session_id = ? AND client_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (session_id, cid, session_id, cid, self.max_messages),
            )
            
            # --- ARCHIVADO EN DIARIO DE SESIONES ---
            from datetime import datetime
            import json
            if self.is_testing:
                date_str = session_id
            else:
                date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
            
            row = conn.execute("SELECT messages FROM session_diary WHERE date = ?", (date_str,)).fetchone()
            if row and row["messages"]:
                try:
                    archived = json.loads(row["messages"])
                except Exception:
                    archived = []
            else:
                archived = []
                
            archived.append({
                "role": role,
                "content": content,
                "created_at": datetime.now().isoformat()
            })
            
            conn.execute(
                """
                INSERT INTO session_diary (date, summary, messages, updated_at)
                VALUES (?, '', ?, datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    messages = ?,
                    updated_at = datetime('now')
                """,
                (date_str, json.dumps(archived, ensure_ascii=False), json.dumps(archived, ensure_ascii=False))
            )
            conn.commit()

    def get_history(self, session_id: str, client_id: str | None = None) -> List[Dict[str, str]]:
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._ensure_loaded(session_id, client_id)
        return list(self._cache.get(cache_key, []))

    def get_summary(self, session_id: str, client_id: str | None = None) -> str:
        history = self.get_history(session_id, client_id)
        if not history:
            return ""
        return "\n".join(f"{entry['role']}: {entry['content']}" for entry in history)

    def clear(self, session_id: str, client_id: str | None = None) -> None:
        session_id = self._resolve_session_id(session_id)
        cid = client_id or "default"
        cache_key = f"{session_id}:{cid}"
        self._cache.pop(cache_key, None)
        with _get_connection(cid) as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ? AND client_id = ?", (session_id, cid))
            from datetime import datetime
            if self.is_testing:
                date_str = session_id
            else:
                date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
            conn.execute("DELETE FROM session_diary WHERE date = ?", (date_str,))
            conn.commit()

    def update_summary(self, session_id: str, summary: str, client_id: str | None = None) -> None:
        session_id = self._resolve_session_id(session_id)
        from datetime import datetime
        if self.is_testing:
            date_str = session_id
        else:
            date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            conn.execute(
                """
                INSERT INTO session_diary (date, summary, messages, updated_at)
                VALUES (?, ?, '[]', datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    summary = ?,
                    updated_at = datetime('now')
                """,
                (date_str, summary, summary)
            )
            conn.commit()

    def get_diary_entry(self, session_id: str, client_id: str | None = None) -> dict | None:
        session_id = self._resolve_session_id(session_id)
        from datetime import datetime
        if self.is_testing:
            date_str = session_id
        else:
            date_str = session_id.replace("daily_", "") if "daily_" in session_id else datetime.now().strftime("%Y-%m-%d")
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            row = conn.execute(
                "SELECT date, summary, messages, created_at, updated_at FROM session_diary WHERE date = ?",
                (date_str,)
            ).fetchone()
        if row:
            return {
                "date": row["date"],
                "summary": row["summary"],
                "messages": row["messages"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None

    def list_sessions(self, client_id: str | None = None) -> List[str]:
        """Devuelve todos los session_id con historial guardado."""
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            rows = conn.execute(
                "SELECT DISTINCT session_id FROM messages WHERE client_id = ? ORDER BY session_id",
                (cid,)
                ).fetchall()
        return [r["session_id"] for r in rows]

    def upsert_metadata(self, session_id: str, title: str, discipline: str = "general", project_name: str = "default", is_persistent: bool = True, client_id: str | None = None) -> None:
        """Crea o actualiza los metadatos de una conversación."""
        persistent_val = 1 if is_persistent else 0
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            conn.execute(
                """
                INSERT INTO conversation_metadata (session_id, title, discipline, project_name, is_persistent, updated_at)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(session_id) DO UPDATE SET
                    title = excluded.title,
                    discipline = excluded.discipline,
                    project_name = excluded.project_name,
                    is_persistent = excluded.is_persistent,
                    updated_at = datetime('now')
                """,
                (session_id, title, discipline, project_name, persistent_val)
            )
            conn.commit()

    def get_metadata(self, session_id: str, client_id: str | None = None) -> dict | None:
        """Recupera los metadatos de una conversación."""
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            row = conn.execute(
                "SELECT session_id, title, discipline, project_name, is_persistent, created_at, updated_at FROM conversation_metadata WHERE session_id = ?",
                (session_id,)
            ).fetchone()
        if row:
            return {
                "session_id": row["session_id"],
                "title": row["title"],
                "discipline": row["discipline"],
                "project_name": row["project_name"],
                "is_persistent": bool(row["is_persistent"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None

    def list_persistent_conversations(self, client_id: str | None = None) -> List[dict]:
        """Devuelve todas las conversaciones marcadas como persistentes."""
        cid = client_id or "default"
        with _get_connection(cid) as conn:
            rows = conn.execute(
                "SELECT session_id, title, discipline, project_name, created_at, updated_at FROM conversation_metadata WHERE is_persistent = 1 ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


# Instancia global compartida por toda la aplicación
memory = SessionMemory()
