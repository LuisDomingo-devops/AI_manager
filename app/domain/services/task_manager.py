import uuid
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
import logging

from app.adapters.memory.memory import _get_connection, tenant_context

logger = logging.getLogger("task_manager")

class TaskManager:
    """
    Gestor de ciclo de vida de tareas en background (Tasks) para procesos asíncronos y flujos largos.
    Estados: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED.
    """

    @classmethod
    def create_task(cls, task_type: str, goal: str = "", payload: Optional[Dict[str, Any]] = None, client_id: Optional[str] = None) -> Dict[str, Any]:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        cid = client_id or tenant_context.get() or "default"
        payload_str = json.dumps(payload or {}, ensure_ascii=False)
        now_str = datetime.now().isoformat()

        with _get_connection(cid) as conn:
            conn.execute("""
                INSERT INTO tasks (id, task_type, status, progress, goal, payload, client_id, created_at, updated_at)
                VALUES (?, ?, 'pending', 0.0, ?, ?, ?, ?, ?)
            """, (task_id, task_type, goal, payload_str, cid, now_str, now_str))
            conn.commit()

        logger.info("Tarea creada: %s (%s) para tenant %s", task_id, task_type, cid)
        return {
            "task_id": task_id,
            "task_type": task_type,
            "status": "pending",
            "progress": 0.0,
            "goal": goal,
            "created_at": now_str
        }

    @classmethod
    def update_task_progress(cls, task_id: str, progress: float, status: str = "running", result: Optional[Dict[str, Any]] = None, error: Optional[str] = None) -> bool:
        cid = tenant_context.get() or "default"
        now_str = datetime.now().isoformat()
        result_str = json.dumps(result, ensure_ascii=False) if result is not None else None

        with _get_connection(cid) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tasks
                SET status = ?, progress = ?, result = COALESCE(?, result), error = COALESCE(?, error), updated_at = ?
                WHERE id = ?
            """, (status, float(progress), result_str, error, now_str, task_id))
            conn.commit()
            return cursor.rowcount > 0

    @classmethod
    def complete_task(cls, task_id: str, result: Optional[Dict[str, Any]] = None) -> bool:
        return cls.update_task_progress(task_id, progress=1.0, status="completed", result=result)

    @classmethod
    def fail_task(cls, task_id: str, error: str) -> bool:
        return cls.update_task_progress(task_id, progress=1.0, status="failed", error=error)

    @classmethod
    def get_task(cls, task_id: str) -> Optional[Dict[str, Any]]:
        cid = tenant_context.get() or "default"
        with _get_connection(cid) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, task_type, status, progress, goal, payload, result, error, client_id, created_at, updated_at
                FROM tasks
                WHERE id = ?
            """, (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "id": row["id"],
                "task_type": row["task_type"],
                "status": row["status"],
                "progress": float(row["progress"]),
                "goal": row["goal"],
                "payload": json.loads(row["payload"]) if row["payload"] else {},
                "result": json.loads(row["result"]) if row["result"] else None,
                "error": row["error"],
                "client_id": row["client_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }

    @classmethod
    def list_tasks(cls, status: Optional[str] = None, client_id: Optional[str] = None) -> List[Dict[str, Any]]:
        cid = client_id or tenant_context.get() or "default"
        with _get_connection(cid) as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("""
                    SELECT id, task_type, status, progress, goal, payload, result, error, client_id, created_at, updated_at
                    FROM tasks
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (status,))
            else:
                cursor.execute("""
                    SELECT id, task_type, status, progress, goal, payload, result, error, client_id, created_at, updated_at
                    FROM tasks
                    ORDER BY created_at DESC
                """)
            rows = cursor.fetchall()
            return [
                {
                    "id": r["id"],
                    "task_type": r["task_type"],
                    "status": r["status"],
                    "progress": float(r["progress"]),
                    "goal": r["goal"],
                    "payload": json.loads(r["payload"]) if r["payload"] else {},
                    "result": json.loads(r["result"]) if r["result"] else None,
                    "error": r["error"],
                    "client_id": r["client_id"],
                    "created_at": r["created_at"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]
