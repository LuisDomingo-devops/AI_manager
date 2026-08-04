import logging
from typing import List
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("guardian_websocket")

class GuardianWebSocketManager:
    """
    Gestor de conexiones WebSocket para la extensión del navegador Alfonso Guardián.
    Permite enviar alertas, bloquear acciones y rellenar datos en la AEAT/SS.
    """
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Extensión Guardián conectada. Conexiones activas: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Extensión Guardián desconectada. Conexiones activas: {len(self.active_connections)}")

    async def send_json(self, message: dict):
        """Envía un mensaje JSON a todas las extensiones conectadas."""
        logger.info(f"Enviando mensaje a la extensión: {message}")
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error enviando mensaje a la extensión: {e}")

    async def request_action(self, action: str, params: dict) -> dict:
        """
        Envía un comando a la extensión y espera una respuesta (si es necesario).
        """
        message = {
            "action": action,
            "params": params
        }
        await self.send_json(message)
        return {"status": "sent"}

guardian_ws_manager = GuardianWebSocketManager()
