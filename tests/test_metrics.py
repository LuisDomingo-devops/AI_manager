import pytest
import os
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings
from app.infrastructure.monitoring.metrics_service import MetricsService

@pytest.fixture(autouse=True)
def setup_test_db():
    os.environ["TESTING"] = "true"
    settings.ALFONSO_API_KEY = "test_api_key_default"
    
    # Limpiar tabla de métricas
    from app.adapters.memory.memory import _get_connection
    MetricsService._db_initialized = False
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS llm_metrics_log")
        conn.commit()

def test_metrics_logging_and_api():
    # 1. Loggear un par de métricas de forma programática
    MetricsService.log_llm_metrics(
        client_id="test_client",
        model_name="mock-deepseek",
        prompt_tokens=1000,
        completion_tokens=500,
        latency_ms=250,
        request_id="req-1"
    )
    MetricsService.log_llm_metrics(
        client_id="test_client",
        model_name="mock-deepseek",
        prompt_tokens=2000,
        completion_tokens=1000,
        latency_ms=450,
        request_id="req-2"
    )
    
    # 2. Consultar el sumario mediante el servicio
    summary = MetricsService.get_llm_metrics_summary(client_id="test_client")
    assert summary["total_calls"] == 2
    assert summary["total_prompt_tokens"] == 3000
    assert summary["total_completion_tokens"] == 1500
    assert summary["avg_latency_ms"] == 350.0
    
    # Coste aproximado: 
    # (3000 * 2.50 / 1e6) + (1500 * 10.00 / 1e6) = 0.0075 + 0.015 = 0.0225 €
    assert summary["total_cost_euros"] == 0.0225

    # 3. Consultar mediante la API HTTP (usando X-API-Key que hace fallback a tenant default/test_client en tests)
    # Para simular el contexto correcto, podemos loggear otra métrica bajo client_id "default"
    MetricsService.log_llm_metrics(
        client_id="default",
        model_name="mock-gemini",
        prompt_tokens=500,
        completion_tokens=100,
        latency_ms=150,
        request_id="req-3"
    )
    
    client = TestClient(app)
    resp = client.get("/monitoring/metrics", headers={"X-API-Key": "test_api_key_default"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["client_id"] == "default"
    assert body["metrics"]["total_calls"] == 1
    assert body["metrics"]["total_prompt_tokens"] == 500
    assert body["metrics"]["total_completion_tokens"] == 100
