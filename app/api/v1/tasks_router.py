from fastapi import APIRouter, Depends, HTTPException
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.api.routes import verify_api_key
from app.domain.services.task_manager import TaskManager

router = APIRouter(prefix="/tasks", dependencies=[Depends(verify_api_key)])

class TaskCreateRequest(BaseModel):
    task_type: str
    goal: str = ""
    payload: Optional[Dict[str, Any]] = None

@router.get("/")
async def list_tasks_endpoint(status: Optional[str] = None):
    """Lista las tareas en background y su progreso."""
    tasks = TaskManager.list_tasks(status=status)
    return {"status": "ok", "total": len(tasks), "tasks": tasks}

@router.post("/")
async def create_task_endpoint(req: TaskCreateRequest):
    """Crea una nueva tarea asíncrona en segundo plano."""
    return TaskManager.create_task(
        task_type=req.task_type,
        goal=req.goal,
        payload=req.payload
    )

@router.get("/{task_id}")
async def get_task_endpoint(task_id: str):
    """Obtiene el estado, progreso y resultados de una tarea por su ID."""
    task = TaskManager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Tarea {task_id} no encontrada.")
    return {"status": "ok", "task": task}
