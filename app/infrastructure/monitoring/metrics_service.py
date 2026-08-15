import sqlite3
import threading
from datetime import datetime
from typing import Dict, Any
from app.adapters.memory.memory import _get_connection
from app.utils.logger import app_logger

class MetricsService:
    _lock = threading.Lock()
    _db_initialized = False

    # Estimación de coste por millón de tokens (por ejemplo, GPT-4o o similar)
    # Entrada: 2.50 € / M tokens, Salida: 10.00 € / M tokens
    COST_PROMPT_1M = 2.50
    COST_COMPLETION_1M = 10.00

    @classmethod
    def init_metrics_schema(cls) -> None:
        """Inicializa la tabla de métricas de consumo de LLM."""
        if cls._db_initialized:
            return
        with cls._lock:
            if cls._db_initialized:
                return
            conn = _get_connection()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS llm_metrics_log (
                        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id          TEXT NOT NULL,
                        model_name         TEXT NOT NULL,
                        prompt_tokens      INTEGER NOT NULL,
                        completion_tokens  INTEGER NOT NULL,
                        cost_estimate      REAL NOT NULL,
                        latency_ms         INTEGER NOT NULL,
                        request_id         TEXT,
                        created_at         TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.commit()
                cls._db_initialized = True
            finally:
                conn.close()

    @classmethod
    def log_llm_metrics(
        cls,
        client_id: str,
        model_name: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        request_id: str = None
    ) -> None:
        """Registra una llamada del LLM en el histórico de métricas."""
        cls.init_metrics_schema()
        
        # Calcular coste estimado en euros
        cost = (
            (prompt_tokens * (cls.COST_PROMPT_1M / 1_000_000.0)) +
            (completion_tokens * (cls.COST_COMPLETION_1M / 1_000_000.0))
        )
        cost = round(cost, 6)
        
        timestamp = datetime.now().isoformat()
        cid = client_id.strip().lower() if client_id else "global"
        
        conn = _get_connection()
        try:
            conn.execute("""
                INSERT INTO llm_metrics_log (
                    client_id, model_name, prompt_tokens, completion_tokens, cost_estimate, latency_ms, request_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cid, model_name, int(prompt_tokens), int(completion_tokens), cost, int(latency_ms), request_id, timestamp))
            conn.commit()
        finally:
            conn.close()
            
        app_logger.info(
            f"Metrics Logged: Tenant={cid}, Model={model_name}, "
            f"Tokens={prompt_tokens}+{completion_tokens}, Cost={cost}€, Latency={latency_ms}ms"
        )

    @classmethod
    def get_llm_metrics_summary(cls, client_id: str = None) -> Dict[str, Any]:
        """Obtiene agregados de latencia, coste y número de tokens consumidos por tenant."""
        cls.init_metrics_schema()
        query = """
            SELECT 
                COUNT(*) as total_calls,
                SUM(prompt_tokens) as total_prompt_tokens,
                SUM(completion_tokens) as total_completion_tokens,
                SUM(cost_estimate) as total_cost,
                AVG(latency_ms) as avg_latency
            FROM llm_metrics_log
        """
        params = []
        if client_id:
            query += " WHERE client_id = ?"
            params.append(client_id.strip().lower())
            
        conn = _get_connection()
        try:
            row = conn.execute(query, params).fetchone()
        finally:
            conn.close()
            
        if not row or row["total_calls"] == 0:
            return {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_cost_euros": 0.0,
                "avg_latency_ms": 0.0
            }
            
        return {
            "total_calls": row["total_calls"],
            "total_prompt_tokens": row["total_prompt_tokens"] or 0,
            "total_completion_tokens": row["total_completion_tokens"] or 0,
            "total_cost_euros": round(row["total_cost"] or 0.0, 4),
            "avg_latency_ms": round(row["avg_latency"] or 0.0, 2)
        }
