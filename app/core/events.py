import asyncio
from typing import Callable, Dict, List, Any, Optional
from app.utils.logger import app_logger

class EventBus:
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None

    def subscribe(self, event_type: str, listener: Callable):
        if event_type not in self._listeners:
            self._listeners[event_type] = []
        if listener not in self._listeners[event_type]:
            self._listeners[event_type].append(listener)
            app_logger.info(f"Listener '{listener.__name__}' registrado para el evento: '{event_type}'")

    async def publish(self, event_type: str, data: Any):
        await self._queue.put((event_type, data))
        app_logger.debug(f"Evento publicado y encolado: {event_type}")

    def start(self):
        # Recreate Queue in the current running event loop to avoid cross-loop issues in tests/lifespans
        self._queue = asyncio.Queue()
        if self._worker_task is not None:
            self._worker_task.cancel()
        self._worker_task = asyncio.create_task(self._worker_loop())
        app_logger.info("Worker del EventBus iniciado en segundo plano.")

    async def stop(self):
        if self._worker_task is None:
            return
        self._worker_task.cancel()
        try:
            # Catch different event loop errors commonly thrown in test teardowns
            await self._worker_task
        except (asyncio.CancelledError, RuntimeError):
            pass
        finally:
            self._worker_task = None
            app_logger.info("Worker del EventBus detenido.")

    async def _worker_loop(self):
        while True:
            try:
                event_type, data = await self._queue.get()
                listeners = self._listeners.get(event_type, [])
                for listener in listeners:
                    try:
                        if asyncio.iscoroutinefunction(listener):
                            await listener(data)
                        else:
                            listener(data)
                    except Exception as e:
                        app_logger.error(f"Error procesando listener '{listener.__name__}' para '{event_type}': {str(e)}", exc_info=True)
                self._queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                app_logger.error(f"Error en el bucle principal del EventBus: {str(e)}", exc_info=True)

event_bus = EventBus()
