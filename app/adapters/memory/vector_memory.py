"""Fachada de compatibilidad hacia atrás para memoria vectorial (DEPRECATED).

Módulo declarado formalmente obsoleto. Se conserva temporalmente para evitar rotura
de dependencias heredadas. Debe importarse directamente desde
'app.infrastructure.database.memory.vector_memory'.
"""

import warnings

warnings.warn(
    "El módulo 'app.adapters.memory.vector_memory' está obsoleto y será eliminado próximamente. "
    "Importe directamente desde 'app.infrastructure.database.memory.vector_memory'.",
    category=DeprecationWarning,
    stacklevel=2,
)

from app.infrastructure.database.memory.vector_memory import *
