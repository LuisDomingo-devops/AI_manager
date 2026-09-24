import pytest
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from client.core.api_client import AlfonsoAPI
import requests

class ContractAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.server.requests_received.append({
            "method": "GET",
            "path": self.path,
            "headers": dict(self.headers),
            "body": b""
        })
        self._send_configured_response()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        self.server.requests_received.append({
            "method": "POST",
            "path": self.path,
            "headers": dict(self.headers),
            "body": post_data
        })
        self._send_configured_response()

    def do_PUT(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""
        self.server.requests_received.append({
            "method": "PUT",
            "path": self.path,
            "headers": dict(self.headers),
            "body": post_data
        })
        self._send_configured_response()

    def do_DELETE(self):
        self.server.requests_received.append({
            "method": "DELETE",
            "path": self.path,
            "headers": dict(self.headers),
            "body": b""
        })
        self._send_configured_response()

    def _send_configured_response(self):
        status_code = getattr(self.server, "next_status_code", 200)
        body_data = getattr(self.server, "next_body", json.dumps({"status": "ok"}))
        content_type = getattr(self.server, "next_content_type", "application/json")
        
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(body_data.encode('utf-8') if isinstance(body_data, str) else body_data)
        
    def log_message(self, format, *args):
        pass

@pytest.fixture
def contract_server():
    server = HTTPServer(('127.0.0.1', 0), ContractAPIHandler)
    server.requests_received = []
    server.next_status_code = 200
    server.next_body = json.dumps({"status": "ok"})
    server.next_content_type = "application/json"
    
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    yield server
    
    server.shutdown()
    server.server_close()
    thread.join(timeout=1)

@pytest.fixture
def api_client(contract_server):
    port = contract_server.server_port
    return AlfonsoAPI(base_url=f"http://127.0.0.1:{port}", api_key="test_api_key")


# === TESTS DE CONTRATO ===

def test_contract_get_health_valid(api_client, contract_server):
    """Prueba GET /health 200 OK"""
    contract_server.next_status_code = 200
    
    result = api_client.ping()
    
    assert result is True
    assert len(contract_server.requests_received) > 0
    req = contract_server.requests_received[0]
    assert req["method"] == "GET"
    assert req["path"] == "/health"
    assert req["headers"].get("X-API-Key") == "test_api_key"

def test_contract_get_health_5xx(api_client, contract_server):
    """Prueba GET /health 500 error, verifica reintentos implícitos"""
    contract_server.next_status_code = 500
    
    result = api_client.ping()
    
    assert result is False
    assert len(contract_server.requests_received) == 2

def test_contract_send_chat_valid(api_client, contract_server):
    """Prueba POST /chat (sin stream) envía payload correcto y header de sesión."""
    contract_server.next_body = json.dumps({"status": "ok", "response": "Hola"})
    
    result = api_client.send_chat("Test message", session_id="ses_123", stream=False)
    
    assert result == {"status": "ok", "response": "Hola"}
    req = contract_server.requests_received[0]
    assert req["method"] == "POST"
    assert req["path"] == "/chat"
    assert req["headers"].get("X-Session-ID") == "ses_123"
    
    body = json.loads(req["body"].decode('utf-8'))
    assert body["message"] == "Test message"
    assert body["stream"] is False

def test_contract_send_chat_4xx(api_client, contract_server):
    """Prueba POST /chat 400 Bad Request es atrapado y devuelto como dict estructurado."""
    contract_server.next_status_code = 400
    contract_server.next_body = "Bad Request"
    
    result = api_client.send_chat("Test message", session_id="ses_123", stream=False)
    
    assert result["status"] == "error"
    assert "400 Client Error" in result["message"]

def test_contract_get_emails_valid(api_client, contract_server):
    """Prueba GET /mail/emails transmite correctamente params."""
    contract_server.next_body = json.dumps([{"id": 1, "subject": "Test"}])
    
    result = api_client.get_emails(category="WORK", importance="HIGH")
    
    assert len(result) == 1
    assert result[0]["id"] == 1
    
    req = contract_server.requests_received[0]
    assert req["method"] == "GET"
    assert req["path"].startswith("/mail/emails?")
    assert "category=WORK" in req["path"]
    assert "importance=HIGH" in req["path"]

def test_contract_get_emails_5xx_returns_empty(api_client, contract_server):
    """Prueba GET /mail/emails silencia el error y devuelve [] según el contrato existente."""
    contract_server.next_status_code = 500
    
    result = api_client.get_emails()
    
    assert result == []

def test_contract_get_email_5xx_returns_error_dict(api_client, contract_server):
    """Prueba GET /mail/emails/{id} devuelve dict de error en fallo a diferencia del listado."""
    contract_server.next_status_code = 500
    
    result = api_client.get_email(email_id=99)
    
    assert isinstance(result, dict)
    assert result["status"] == "error"
    assert "500 Server Error" in result["message"]

def test_contract_stt_file_upload(api_client, contract_server):
    """Prueba POST /stt envía formData correctamente."""
    contract_server.next_body = json.dumps({"text": "hola"})
    
    result = api_client.stt(b"fake_audio_bytes")
    
    assert result == {"text": "hola"}
    req = contract_server.requests_received[0]
    assert req["method"] == "POST"
    assert req["path"] == "/stt"
    assert "multipart/form-data" in req["headers"].get("Content-Type", "")
    assert b"fake_audio_bytes" in req["body"]

def test_contract_generic_get_exception(api_client, contract_server):
    """Prueba genérico `get` lanza su propia Exception en 5xx."""
    contract_server.next_status_code = 500
    
    with pytest.raises(Exception, match="API GET error: 500 Server Error"):
        api_client.get("/test/generic")

def test_contract_dashboard_sync_invalid_json(api_client, contract_server):
    """Prueba que si la respuesta de /dashboard/sync (200 OK) no es JSON,
       el comportamiento depende de si requests.exceptions.JSONDecodeError es capturada."""
    contract_server.next_status_code = 200
    contract_server.next_body = "Not a JSON"
    contract_server.next_content_type = "text/plain"
    
    try:
        result = api_client.get_dashboard_sync()
        # En versiones recientes de requests, JSONDecodeError hereda de RequestException
        if "status" in result and result["status"] == "error":
            assert "Expecting value" in result["message"] or "JSON" in result["message"]
    except Exception as e:
        # En versiones antiguas, revienta con ValueError o json.decoder.JSONDecodeError
        assert "Expecting value" in str(e) or "JSON" in str(e)

def test_contract_send_chat_sse_generator_error(api_client, contract_server):
    """
    CONTRACT UNDEFINED:
    Si hay una desconexión mientras se itera el generador SSE de send_chat(),
    el bloque `except Exception as e:` inicial de send_chat ya finalizó porque devolvió
    el generador de manera síncrona. La iteración fallará al consumidor, sin empaquetarse
    en un dict controlado. Comprobamos este comportamiento.
    """
    # Para simular, hacemos que iter_lines lance error
    contract_server.next_status_code = 200
    contract_server.next_body = "data: {\"test\": 1}\n\n"
    
    gen = api_client.send_chat("Test stream", session_id="ses_456", stream=True)
    assert hasattr(gen, '__iter__')
    
    # Consumir un elemento con mock del iter_lines
    from unittest.mock import patch
    with patch("requests.models.Response.iter_lines", side_effect=requests.exceptions.ChunkedEncodingError("Network drop")):
        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            list(gen)
