import os
import pytest
from pathlib import Path
from app.adapters.memory.memory import _get_connection
from app.utils.encryption import encryptor
from app.tools.server.billing_tools import generate_invoice_pdf
from app.domain.services.verifactu_service import VerifactuService

@pytest.mark.asyncio
async def test_invoice_draft_creation_and_finalization():
    # 1. Crear una factura incompleta (falta NIF) -> debe ser borrador
    res_draft = await generate_invoice_pdf(
        client_name="Cliente de Prueba S.L.",
        client_nif="", # NIF vacío
        amount=100.0,
        concept="Servicios de desarrollo de software",
        date="15/07/2026"
    )
    
    assert res_draft["status"] == "ok"
    assert res_draft["is_draft"] is True
    draft_id = res_draft["invoice_id"]
    assert draft_id.startswith("BORRADOR-")
    
    # Comprobar en base de datos que está guardado como borrador
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, invoice_id, receiver_name, receiver_nif, status FROM invoices")
        rows = cursor.fetchall()
        found_draft = False
        for r in rows:
            dec_id = encryptor.decrypt(r["invoice_id"])
            if dec_id == draft_id:
                found_draft = True
                assert r["status"] == "borrador"
                assert encryptor.decrypt(r["receiver_name"]) == "Cliente de Prueba S.L."
                assert encryptor.decrypt(r["receiver_nif"]) == ""
                break
        assert found_draft is True
    finally:
        conn.close()

    # Comprobar que no se ha registrado en Verifactu
    # No debería haber registrado esta factura en Verifactu
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verifactu_invoices WHERE invoice_number = ?", (draft_id,))
        count = cursor.fetchone()[0]
        assert count == 0
    finally:
        conn.close()

    # 2. Completar el borrador -> proporcionando el NIF faltante
    res_firm = await generate_invoice_pdf(
        client_name="Cliente de Prueba S.L.",
        client_nif="B12345678", # NIF completo
        amount=100.0,
        concept="Servicios de desarrollo de software",
        invoice_id=draft_id, # ID del borrador a completar
        date="15/07/2026"
    )

    assert res_firm["status"] == "ok"
    assert res_firm["is_draft"] is False
    firm_id = res_firm["invoice_id"]
    assert firm_id.startswith("F-")

    # Comprobar en base de datos que el borrador fue actualizado y ahora es firme
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, invoice_id, receiver_name, receiver_nif, status FROM invoices")
        rows = cursor.fetchall()
        
        # El ID anterior de borrador no debe existir más o el registro original debe haber sido actualizado a F-
        found_draft_after = False
        found_firm_after = False
        for r in rows:
            dec_id = encryptor.decrypt(r["invoice_id"])
            if dec_id == draft_id:
                found_draft_after = True
            if dec_id == firm_id:
                found_firm_after = True
                assert r["status"] == "firmada"
                assert encryptor.decrypt(r["receiver_nif"]) == "B12345678"
        
        assert found_draft_after is False
        assert found_firm_after is True
    finally:
        conn.close()

    # Comprobar que ahora sí se registró en Verifactu
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM verifactu_invoices WHERE invoice_number = ?", (firm_id,))
        count = cursor.fetchone()[0]
        assert count == 1
    finally:
        conn.close()

    # Limpiar PDFs generados
    if "pdf_path" in res_firm and os.path.exists(res_firm["pdf_path"]):
        os.remove(res_firm["pdf_path"])
    if "pdf_path" in res_draft and os.path.exists(res_draft["pdf_path"]):
        # Si quedó algún residuo
        try:
            os.remove(res_draft["pdf_path"])
        except Exception:
            pass
