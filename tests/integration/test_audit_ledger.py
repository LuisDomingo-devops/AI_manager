import pytest
import os
import sqlite3
from app.adapters.memory.memory import _get_connection, tenant_context
from app.domain.services.audit_ledger import AuditLedgerService
from app.tools.server.billing_tools import delete_client, create_product

@pytest.fixture(autouse=True)
def clean_test_db():
    # Establecer entorno de test
    os.environ["TESTING"] = "true"
    token = tenant_context.set("test_tenant")
    
    # Limpiar tabla de logs
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS audit_ledger_log")
        conn.execute("DROP TABLE IF EXISTS clients")
        # Re-inicializar esquema de clientes si es necesario
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                nif TEXT NOT NULL
            )
        """)
        conn.commit()
    
    yield
    tenant_context.reset(token)

def test_audit_ledger_flow():
    # 1. Registrar primer evento
    hash1 = AuditLedgerService.log_audit_event("TEST_EVENT_1", "Detalle del evento 1", "test_tenant")
    assert hash1 is not None
    
    # 2. Registrar segundo evento (debería encadenar con hash1)
    hash2 = AuditLedgerService.log_audit_event("TEST_EVENT_2", "Detalle del evento 2", "test_tenant")
    assert hash2 is not None
    assert hash1 != hash2
    
    # Verificar en DB que el prev_hash de event2 sea hash1
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM audit_ledger_log ORDER BY id ASC").fetchall()
        assert len(rows) == 2
        assert rows[0]["prev_hash"] is None or rows[0]["prev_hash"] == ""
        assert rows[1]["prev_hash"] == hash1

    # 3. Validar integridad global
    res = AuditLedgerService.verify_ledger_integrity("test_tenant")
    assert res["status"] == "valid"

def test_audit_ledger_tampering_detection():
    # 1. Registrar eventos
    AuditLedgerService.log_audit_event("MUTATION_1", "Modificación inicial", "test_tenant")
    AuditLedgerService.log_audit_event("MUTATION_2", "Modificación secundaria", "test_tenant")
    
    # Verificar que es válido
    assert AuditLedgerService.verify_ledger_integrity("test_tenant")["status"] == "valid"
    
    # 2. Manipular la DB directamente simulando un ataque o alteración
    with _get_connection() as conn:
        # Cambiar el tipo de evento en el registro 1
        conn.execute("UPDATE audit_ledger_log SET description = 'Ataque malicioso' WHERE id = 1")
        conn.commit()
        
    # 3. Validar integridad -> Debería retornar "corrupted"
    res = AuditLedgerService.verify_ledger_integrity("test_tenant")
    assert res["status"] == "corrupted"
    assert "Alteración de datos detectada" in res["message"]

@pytest.mark.asyncio
async def test_audit_ledger_tool_integration():
    # Registrar un cliente de prueba
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clients (name, nif) VALUES ('LUIS DOMINGO', '12345678Z')")
        client_id = cursor.lastrowid
        conn.commit()
        
    # Eliminar al cliente con la herramienta (confirmado)
    res_del = await delete_client(client_id=client_id, confirmed_by_user=True)
    assert res_del["status"] == "ok"
    
    # Comprobar que se ha creado un registro en el Ledger
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM audit_ledger_log WHERE event_type = 'DELETE_CLIENT'").fetchall()
        assert len(rows) == 1
        assert f"ID {client_id}" in rows[0]["description"]
        
    # Verificar la integridad global del Ledger
    integrity = AuditLedgerService.verify_ledger_integrity("test_tenant")
    assert integrity["status"] == "valid"
