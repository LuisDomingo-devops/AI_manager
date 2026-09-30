"""Fachada de compatibilidad hacia atrás para adaptadores de persistencia.

Reexporta las funciones históricas de acceso a base de datos e incorpora
los nuevos puntos de entrada aislados para el núcleo legal.
"""

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
