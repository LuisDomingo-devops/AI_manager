"""Exportador y Validador de Especificación OpenAPI Local.

Permite generar el esquema JSON contractual para la GUI PyQt6 y la extensión.
"""

from typing import Any, Dict
from fastapi.openapi.utils import get_openapi
from app.main import app


def get_local_openapi_specification() -> Dict[str, Any]:
    """Genera la especificación OpenAPI de los endpoints del backend local."""
    return get_openapi(
        title="Alfonso AI Konta - Local Desktop API",
        version="1.0.0",
        description="Contrato formal de comunicación en bucle invertido (127.0.0.1) para GUI PyQt6 y extensión.",
        routes=app.routes,
    )
