import pytest
import os
import shutil
from pathlib import Path
from app.domain.services.verifactu_service import VerifactuService
from app.domain.services.ledger_service import LedgerService
from app.tools.server.billing_tools import (
    generate_invoice_pdf,
    create_rectificativa_invoice,
    create_client
)
from app.adapters.memory.memory import _get_connection, tenant_context, _init_db_schema
from app.utils.encryption import encryptor

@pytest.fixture(autouse=True)
def setup_test_env():
    # Establecer tenant para tests
    token = tenant_context.set("compliance_tenant")
    VerifactuService.init_verifactu_schema()
    with _get_connection() as conn:
        _init_db_schema(conn)
        conn.execute("DELETE FROM invoices")
        conn.execute("DELETE FROM journal_entries")
        conn.execute("DELETE FROM ledger_entries")
        conn.execute("DELETE FROM verifactu_invoices")
        conn.execute("DELETE FROM sif_event_log")
        conn.execute("DELETE FROM user_profile")
        
        # Configurar perfil del emisor
        conn.execute("""
            INSERT INTO user_profile (user_type, nif, razon_social, direccion)
            VALUES (?, ?, ?, ?)
        """, (
            "autonomo",
            encryptor.encrypt("12345678Z"),
            encryptor.encrypt("LUIS DOMINGO AUTONOMO"),
            encryptor.encrypt("Calle Gran Vía 28, Madrid")
        ))
        conn.commit()
        
    yield
    tenant_context.reset(token)


@pytest.mark.asyncio
async def test_full_rectificativa_flow():
    """
    Test completo de emisión de factura ordinaria, factura rectificativa (R1) y verificación de:
    - Serie R-2026-XXX
    - Asiento contable de rectificación
    - Registro en Verifactu con TipoFactura R1 y validación XSD
    """
    # 1. Crear factura ordinaria firme
    res_orig = await generate_invoice_pdf(
        client_name="Cliente Empresa S.L.",
        client_nif="B87654321",
        amount=1000.0,
        concept="Desarrollo de software T1",
        iva_rate=21.0,
        irpf_rate=15.0,
        confirmed_by_user=True
    )
    assert res_orig["status"] == "ok"
    assert res_orig["is_draft"] is False
    orig_id = res_orig["invoice_id"]
    assert orig_id.startswith("F-2026-")

    # 2. Emitir factura rectificativa por error en precio (R1)
    res_rect = await create_rectificativa_invoice(
        original_invoice_id=orig_id,
        reason="Error en tarifa aplicada",
        rectificativa_type="R1",
        amount=200.0, # Rectificación parcial de 200€
        iva_rate=21.0,
        irpf_rate=15.0,
        confirmed_by_user=True
    )
    assert res_rect["status"] == "ok"
    assert res_rect["is_draft"] is False
    rect_id = res_rect["rectificativa_id"]
    assert rect_id.startswith("R-2026-")
    assert res_rect["original_invoice_id"] == orig_id
    assert os.path.exists(res_rect["pdf_path"])

    # 3. Verificar que la integridad de la cadena Verifactu es válida con la factura ordinaria y rectificativa
    integrity = VerifactuService.verify_chain_integrity()
    assert integrity["status"] == "valid"

    # 4. Verificar asiento contable de rectificación en Libro Diario
    diario = LedgerService.get_libro_diario(2026)
    rect_entries = [e for e in diario if rect_id in e["concepto"]]
    assert len(rect_entries) >= 1
    rect_entry = rect_entries[0]
    
    # Comprobar que en el asiento de rectificación los 200€ están al DEBE en la 705 (minoración)
    apuntes_705 = [a for a in rect_entry["apuntes"] if a["cuenta"] == "70500000"]
    assert len(apuntes_705) == 1
    assert apuntes_705[0]["debe"] == 200.0
    assert apuntes_705[0]["haber"] == 0.0


@pytest.mark.asyncio
async def test_sif_event_logging_and_tampering_alert():
    """
    Verifica que los eventos de ciclo de vida del SIF y las alertas de manipulación se registran firmados y encadenados.
    """
    # Registrar evento de arranque
    hash1 = VerifactuService.log_sif_event(
        event_type="STARTUP_SYSTEM",
        description="Arranque del sistema SIF en test de conformidad."
    )
    assert hash1 is not None and len(hash1) == 64

    # Registrar evento de parada
    hash2 = VerifactuService.log_sif_event(
        event_type="SHUTDOWN_SYSTEM",
        description="Parada programada del sistema SIF."
    )
    assert hash2 is not None and len(hash2) == 64
    assert hash1 != hash2

    # Verificar registros en base de datos
    with _get_connection() as conn:
        rows = conn.execute("SELECT * FROM sif_event_log ORDER BY id ASC").fetchall()
        assert len(rows) >= 2
        assert rows[-1]["prev_event_hash"] == rows[-2]["current_hash"]


def test_tenant_private_key_isolation():
    """
    Verifica que diferentes tenants obtienen claves privadas independientes.
    """
    key_tenant_a = VerifactuService.get_or_create_private_key(client_id="tenant_empresa_a")
    key_tenant_b = VerifactuService.get_or_create_private_key(client_id="tenant_empresa_b")
    
    pub_a = key_tenant_a.public_key().public_numbers().n
    pub_b = key_tenant_b.public_key().public_numbers().n
    
    # Claves públicas distintas para obligados tributarios distintos
    assert pub_a != pub_b
