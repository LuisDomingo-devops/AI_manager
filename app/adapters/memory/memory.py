"""Fachada de compatibilidad hacia atrás para adaptadores de persistencia (DEPRECATED).

Módulo declarado formalmente obsoleto. Se conserva temporalmente para evitar rotura
de dependencias heredadas. Todos los nuevos desarrollos y servicios de producción
deben importar directamente desde 'app.infrastructure.database.connection_manager' o
'app.infrastructure.database.memory'.
"""

import warnings

warnings.warn(
    "El módulo 'app.adapters.memory.memory' está obsoleto y será eliminado próximamente. "
    "Importe directamente desde 'app.infrastructure.database.connection_manager'.",
    category=DeprecationWarning,
    stacklevel=2,
)

from app.infrastructure.database.memory.memory import *
from app.infrastructure.database.connection_manager import (
    _get_connection,
    write_transaction,
    get_readonly_connection,
    init_all_schemas,
    init_all_schemas as _init_db_schema,
    DB_PATH,
    tenant_context,
    IS_TESTING,
)
from app.infrastructure.database.legal_connection import (
    get_legal_connection,
    get_legal_readonly_connection,
    legal_write_transaction,
)

__all__ = [
    "_get_connection",
    "write_transaction",
    "get_readonly_connection",
    "init_all_schemas",
    "_init_db_schema",
    "DB_PATH",
    "tenant_context",
    "IS_TESTING",
    "get_legal_connection",
    "get_legal_readonly_connection",
    "legal_write_transaction",
]
