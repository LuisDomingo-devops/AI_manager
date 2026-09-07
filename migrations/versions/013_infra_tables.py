"""
013_infra_tables.py
====================
Migra la definicion canonica de tablas de infraestructura al MigrationRunner.
Antes estas tablas eran creadas inline en sus respectivos servicios:
  - AuditLedger       -> audit_ledger_log
  - MetricsService    -> llm_metrics_log
  - SessionManager    -> user_sessions

NOTA: Los esquemas son exactamente los que usan los servicios para sus INSERTs/SELECTs.
"""
import sqlite3

VERSION = "013"
DESCRIPTION = "Infraestructura: audit_ledger_log, llm_metrics_log, user_sessions"


def upgrade(conn: sqlite3.Connection) -> None:
    # Schema exacto de AuditLedger (usa: client_id, event_type, description,
    #                                     prev_hash, current_hash, signature)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_ledger_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id       TEXT,
            event_type      TEXT NOT NULL,
            description     TEXT NOT NULL,
            prev_hash       TEXT,
            current_hash    TEXT NOT NULL,
            signature       TEXT NOT NULL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Schema exacto de MetricsService (usa: client_id, model_name, prompt_tokens,
    #                                        completion_tokens, cost_estimate, latency_ms, request_id)
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

    # Schema exacto de SessionManager (usa: token_hash PRIMARY KEY, client_id,
    #                                        created_at, expires_at, revoked)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            token_hash    TEXT PRIMARY KEY,
            client_id     TEXT NOT NULL,
            created_at    TEXT NOT NULL,
            expires_at    TEXT NOT NULL,
            revoked       INTEGER NOT NULL DEFAULT 0
        )
    """)
