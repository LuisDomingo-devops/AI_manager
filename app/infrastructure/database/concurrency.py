"""
Módulo de Concurrencia y Sincronización para SQLite Multi-Tenant.
Feature: specs/020-sqlite-connection-pool-concurrency
Proporciona exclusión mutua a nivel de proceso por inquilino y políticas de reintento deterministas.
"""

import asyncio
import functools
import inspect
import logging
import random
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger("sqlite_concurrency")


@dataclass
class RetryPolicy:
    """Política determinista de reintentos para operaciones que encuentren contención."""
    max_retries: int = 5
    base_delay: float = 0.05
    max_delay: float = 1.0

    def calculate_delay(self, attempt: int) -> float:
        """Calcula el tiempo de espera con retroceso exponencial y variación aleatoria (jitter)."""
        backoff = min(self.max_delay, self.base_delay * (2 ** attempt))
        jitter = random.uniform(0, 0.05)
        return backoff + jitter


class TenantLockRegistry:
    """
    Registro thread-safe de cerrojos de exclusión mutua para transacciones de escritura.
    Garantiza que un único escritor por base de datos de tenant ejecute mutaciones a la vez en Python,
    evitando que SQLite arroje errores nativos de colisión de archivos.
    """
    _instance: Optional["TenantLockRegistry"] = None
    _singleton_lock = threading.Lock()

    def __new__(cls) -> "TenantLockRegistry":
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = super(TenantLockRegistry, cls).__new__(cls)
                cls._instance._locks = {}
                cls._instance._registry_lock = threading.Lock()
            return cls._instance

    def _sanitize_tenant(self, client_id: Optional[str]) -> str:
        cid = (client_id or "default").strip().lower()
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "", cid)
        return sanitized if sanitized else "default"

    def get_lock(self, client_id: Optional[str] = None) -> threading.RLock:
        """
        Retorna el cerrojo reentrante para el tenant especificado.
        Si no existe, lo crea atómicamente.
        """
        tenant_key = self._sanitize_tenant(client_id)
        with self._registry_lock:
            if tenant_key not in self._locks:
                self._locks[tenant_key] = threading.RLock()
            return self._locks[tenant_key]

    def reset(self) -> None:
        """Reinicia los cerrojos registrados (utilizado en testing y limpiezas de contexto)."""
        with self._registry_lock:
            self._locks.clear()


# Instancia singleton del registro de cerrojos
tenant_locks = TenantLockRegistry()


def is_lock_error(exc: Exception) -> bool:
    """Verifica si la excepción corresponde a un bloqueo transitorio de SQLite."""
    if isinstance(exc, sqlite3.OperationalError):
        msg = str(exc).lower()
        if "database is locked" in msg or "database table is locked" in msg or "locked" in msg:
            return True
    return False


def retry_on_db_lock(
    func: Optional[Callable] = None,
    *,
    max_retries: int = 5,
    base_delay: float = 0.05,
    max_delay: float = 1.0
):
    """
    Decorador para funciones o métodos que ejecutan operaciones SQLite sujetas a contención transitoria.
    Soporta funciones síncronas y asíncronas, con o sin argumentos de configuración.
    """
    policy = RetryPolicy(max_retries=max_retries, base_delay=base_delay, max_delay=max_delay)

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                for attempt in range(policy.max_retries + 1):
                    try:
                        return await fn(*args, **kwargs)
                    except Exception as e:
                        if is_lock_error(e) and attempt < policy.max_retries:
                            delay = policy.calculate_delay(attempt)
                            logger.warning(
                                f"Bloqueo en BD detectado en {fn.__name__} (intento {attempt + 1}/{policy.max_retries}). "
                                f"Reintentando en {delay:.3f}s: {e}"
                            )
                            await asyncio.sleep(delay)
                        else:
                            raise
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs) -> Any:
                for attempt in range(policy.max_retries + 1):
                    try:
                        return fn(*args, **kwargs)
                    except Exception as e:
                        if is_lock_error(e) and attempt < policy.max_retries:
                            delay = policy.calculate_delay(attempt)
                            logger.warning(
                                f"Bloqueo en BD detectado en {fn.__name__} (intento {attempt + 1}/{policy.max_retries}). "
                                f"Reintentando en {delay:.3f}s: {e}"
                            )
                            time.sleep(delay)
                        else:
                            raise
            return sync_wrapper

    if func is not None and callable(func):
        return decorator(func)
    return decorator
