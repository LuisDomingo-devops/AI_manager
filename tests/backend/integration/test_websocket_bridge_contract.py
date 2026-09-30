"""Pruebas de integración del contrato de WebSocket Bridge (T037 - TDD).

Valida el intercambio de mensajes y eventos en tiempo real con la extensión y la GUI.
"""

from fastapi.testclient import TestClient
from app.main import app


def test_websocket_guardian_bridge_handshake_and_echo():
    client = TestClient(app)
    
    with client.websocket_connect("/ws/guardian") as ws:
        # Enviar comando de prueba
        payload = {"action": "PING", "source": "gui_client"}
        ws.send_json(payload)
        
        # Recibir respuesta conforme al contrato
        data = ws.receive_json()
        assert data.get("status") == "received"
        assert data.get("echo") == payload
