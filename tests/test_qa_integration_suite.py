import pytest
import os
import shutil
from pathlib import Path
from app.utils.anonymizer import DataAnonymizer
from app.utils.encryption import encryptor
from app.domain.services.tax_parser_service import TaxParserService
from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection, memory
from app.adapters.mail_db import create_email, list_emails

@pytest.fixture(autouse=True)
def clean_system_state(tmp_path, monkeypatch):
    """Limpia el estado de la base de datos de test antes de cada ejecución."""
    import sys
    import app.adapters.memory.memory
    memory_mod = sys.modules["app.adapters.memory.memory"]
    test_db = tmp_path / "memory_test_qa_integration.db"
    monkeypatch.setattr(memory_mod, "DB_PATH", test_db)

    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS messages")
        conn.execute("DROP TABLE IF EXISTS conversation_metadata")
        conn.execute("DROP TABLE IF EXISTS invoices")
        conn.execute("DROP TABLE IF EXISTS emails")
        conn.execute("DROP TABLE IF EXISTS settings")
        conn.execute("DROP TABLE IF EXISTS calendar_events")
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.commit()
        
        # Recrear todas las tablas
        from app.adapters.memory.memory import _init_db_schema
        from app.adapters.mail_db import _init_mail_schema
        from app.adapters.calendar_db import _init_calendar_schema
        from app.domain.services.verifactu_service import VerifactuService
        
        _init_db_schema(conn)
        _init_mail_schema(conn)
        _init_calendar_schema(conn)
        VerifactuService.init_verifactu_schema()
        
    # Reset in-memory cache
    memory._cache.clear()
    yield

def test_integration_tax_parsing_encryption_and_aggregation():
    """
    TEST QA & INTEGRACIÓN 1:
    Verifica que al guardar una factura extraída en la base de datos:
    1. Los datos sensibles se guarden encriptados en disco.
    2. Al consultar los agregados trimestrales, el sistema desencripte en memoria y calcule los totales correctos.
    """
    invoice_data = {
        "invoice_id": "FACT-9999",
        "date": "2026-08-02",
        "issuer_name": "Luis Domingo Pérez",
        "issuer_nif": "12345678Z",
        "receiver_name": "Alfonso Autónomo S.L.",
        "receiver_nif": "B87654321",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 15.0,
        "irpf_amount": 150.0,
        "total_amount": 1060.0,
        "category": "income",
        "quarter": 3,
        "year": 2026
    }
    
    # 1. Guardar la factura
    row_id = TaxParserService.save_invoice_to_db(invoice_data, file_path="facturas/factura_test.pdf")
    assert row_id > 0
    
    # 2. Comprobar que en disco (directo en SQL) los datos están cifrados
    with _get_connection() as conn:
        raw_row = conn.execute("SELECT issuer_name, issuer_nif, base_imponible FROM invoices WHERE id = ?", (row_id,)).fetchone()
        
    assert raw_row["issuer_name"] != "Luis Domingo Pérez"
    assert raw_row["issuer_nif"] != "12345678Z"
    assert raw_row["base_imponible"] != 1000.0
    
    # 3. Comprobar que el descifrado y agregados funcionan correctamente
    aggregates = TaxParserService.get_quarterly_aggregates(year=2026)
    assert len(aggregates) == 1
    agg = aggregates[0]
    assert agg["year"] == 2026
    assert agg["quarter"] == 3
    assert agg["income"]["base"] == 1000.0
    assert agg["income"]["iva"] == 210.0
    assert agg["income"]["total"] == 1060.0


def test_integration_anonymization_and_llm_payload_safety():
    """
    TEST QA & INTEGRACIÓN 2:
    Verifica que un payload sensible (con nombre, DNI, teléfono, IBAN y correos):
    1. Se anonimice correctamente reemplazando los campos con tokens seguros.
    2. El mapa reversible asocie exactamente los valores originales.
    3. Al retornar la respuesta simulada del LLM, se detokenice con éxito.
    """
    anonymizer = DataAnonymizer()
    sensitive_prompt = (
        "Hola, soy don Francisco Javier. Mi NIF es 87654321A y mi número de teléfono "
        "es +34 655444333. Necesito que transfieras 500€ a la cuenta ES12 3456 7890 12 3456789012. "
        "Cualquier consulta escríbeme a francisco@empresa.com"
    )
    
    # 1. Anonimizar
    anon_prompt, mapping = anonymizer.anonymize(sensitive_prompt)
    
    assert "[NOMBRE_1]" in anon_prompt
    assert "[NIF_1]" in anon_prompt
    assert "[TELEFONO_1]" in anon_prompt
    assert "[IBAN_1]" in anon_prompt
    assert "[EMAIL_1]" in anon_prompt
    assert "Francisco Javier" in mapping.values()
    assert "87654321A" in mapping.values()
    assert "+34 655444333" in mapping.values()
    assert "ES12 3456 7890 12 3456789012" in mapping.values()
    assert "francisco@empresa.com" in mapping.values()
    
    # 2. Simular respuesta del LLM haciendo referencia a los tokens
    llm_simulated_response = "Entendido [NOMBRE_1], procesando transferencia de [IMPORTE_1] al IBAN [IBAN_1]."
    
    # 3. Recuperar datos originales (detokenización)
    final_user_response = anonymizer.detokenize(llm_simulated_response, mapping)
    
    assert "Francisco Javier" in final_user_response
    assert "ES12 3456 7890 12 3456789012" in final_user_response
    assert "500€" in final_user_response


def test_integration_verifactu_cryptographic_chaining():
    """
    TEST QA & INTEGRACIÓN 3:
    Verifica el flujo técnico Verifactu 2027:
    1. Registra múltiples facturas.
    2. Comprueba que el hash actual de la factura N sea el 'prev_hash' de la factura N+1.
    3. Comprueba que la validación de integridad detecte cualquier alteración fraudulenta.
    """
    fac1 = {
        "invoice_number": "EMITIDA-001",
        "date_of_issue": "2026-08-01",
        "issuer_nif": "B12345678",
        "receiver_nif": "12345678Z",
        "base_imponible": 500.0,
        "iva_amount": 105.0,
        "total_amount": 605.0
    }
    fac2 = {
        "invoice_number": "EMITIDA-002",
        "date_of_issue": "2026-08-02",
        "issuer_nif": "B12345678",
        "receiver_nif": "87654321A",
        "base_imponible": 800.0,
        "iva_amount": 168.0,
        "total_amount": 968.0
    }
    
    res1 = VerifactuService.register_invoice(fac1)
    res2 = VerifactuService.register_invoice(fac2)
    
    assert res1["prev_hash"] is None
    assert res2["prev_hash"] == res1["current_hash"]
    
    # Validar integridad inicial
    audit = VerifactuService.verify_chain_integrity()
    assert audit["status"] == "valid"
    
    # Intentar alterar un registro en base de datos directamente
    with _get_connection() as conn:
        conn.execute("UPDATE verifactu_invoices SET base_imponible = 99.0 WHERE invoice_number = 'EMITIDA-001'")
        conn.commit()
        
    # Verificar que el sistema detecta la alteración del hash de encadenamiento
    corrupted_audit = VerifactuService.verify_chain_integrity()
    assert corrupted_audit["status"] in ("tampered", "corrupted")


def test_integration_mail_database_encryption_and_retrieval():
    """
    TEST QA & INTEGRACIÓN 4:
    Verifica que la base de datos de correos electrónicos encripte y desencripte correctamente:
    1. Creamos un email con contenido confidencial.
    2. Verificamos que esté cifrado en disco.
    3. Verificamos que se recupere completamente descifrado al listarlo o pedir detalle.
    """
    mail_id = create_email(
        sender="Hacienda Pública <notificaciones@aeat.es>",
        recipient="luisd@alfonso.dev",
        subject="Requerimiento de IVA ejercicio 2025",
        body="Se solicita aportación de los libros de facturas del ejercicio fiscal 2025 en el plazo improrrogable de 10 días.",
        received_at="2026-08-02 10:00",
        category="legal",
        importance="Alta",
        summary="Requerimiento AEAT sobre IVA 2025."
    )
    
    assert mail_id > 0
    
    # Comprobar cifrado en disco
    from app.adapters.mail_db import get_connection as get_mail_connection
    with get_mail_connection() as conn:
        raw_mail = conn.execute("SELECT sender, body FROM emails WHERE id = ?", (mail_id,)).fetchone()
    assert raw_mail["sender"] != "Hacienda Pública <notificaciones@aeat.es>"
    assert raw_mail["body"] != "Se solicita aportación de los libros de facturas del ejercicio fiscal 2025 en el plazo improrrogable de 10 días."
    
    # Comprobar descifrado al consultar
    emails = list_emails(category="legal")
    email = next((m for m in emails if m["subject"] == "Requerimiento de IVA ejercicio 2025"), None)
    assert email is not None
    assert email["sender"] == "Hacienda Pública <notificaciones@aeat.es>"
    assert "requerimiento judicial" not in email["body"]
    assert "Se solicita aportación de los libros" in email["body"]
    assert email["summary"] == "Requerimiento AEAT sobre IVA 2025."
