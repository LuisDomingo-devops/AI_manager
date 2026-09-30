import re
import contextlib
from typing import Generator, Optional
from app.infrastructure.database.connection_manager import (
    tenant_context as cm_tenant_context,
    reset_thread_local_pool,
)

def sanitize_tenant_id(tenant_id: Optional[str]) -> str:
    """
    Sanitiza el identificador de la empresa para evitar caracteres de ruta peligrosos
    o inyecciones en el nombre del archivo de base de datos SQLite.
    """
    if not tenant_id:
        return "default"
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "", str(tenant_id).strip().lower())
    return cleaned if cleaned else "default"

def get_current_tenant() -> str:
    """Devuelve el identificador de la empresa o perfil contable activo en el contexto actual."""
    try:
        return cm_tenant_context.get()
    except LookupError:
        return "default"

def set_current_tenant(tenant_id: str) -> str:
    """
    Establece la empresa o perfil contable activo de forma aislada para el hilo/corutina actual.
    Limpia conexiones previas si se cambia de empresa para evitar reutilización cruzada.
    """
    sanitized = sanitize_tenant_id(tenant_id)
    prev = get_current_tenant()
    if prev != sanitized:
        reset_thread_local_pool()
    cm_tenant_context.set(sanitized)
    return sanitized

@contextlib.contextmanager
def tenant_scope(tenant_id: str) -> Generator[str, None, None]:
    """
    Context manager seguro para ejecutar un bloque de código bajo el perfil de una empresa específica.
    Restaura automáticamente el perfil anterior al finalizar o ante excepciones.
    """
    prev_tenant = get_current_tenant()
    token = cm_tenant_context.set(sanitize_tenant_id(tenant_id))
    reset_thread_local_pool()
    try:
        yield cm_tenant_context.get()
    finally:
        cm_tenant_context.reset(token)
        reset_thread_local_pool()

class TenantManager:
    """Fachada para la gestión y consulta de perfiles multi-empresa locales."""
    @staticmethod
    def get_current() -> str:
        return get_current_tenant()

    @staticmethod
    def switch(tenant_id: str) -> str:
        return set_current_tenant(tenant_id)

    @staticmethod
    def scope(tenant_id: str):
        return tenant_scope(tenant_id)
