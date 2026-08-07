import os
import sys
import logging
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from lxml import etree

from app.domain.services.verifactu_service import VerifactuService
from app.adapters.memory.memory import _get_connection, memory
from app.domain.services.tax_parser_service import TaxParserService
from app.tools.server.aeat_automation_tools import (
    generate_modelo_303_autofill_script,
    generate_modelo_130_autofill_script,
    generate_modelo_111_autofill_script,
    generate_modelo_115_autofill_script,
    generate_modelo_202_autofill_script,
    generate_modelo_390_summary,
    generate_modelo_347_summary
)
from app.domain.planner_orchestrator import PlannerOrchestrator
from app.adapters.mail_db import create_email

# 1. Configuración de rutas de certificados de prueba
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CERT_PATH = str(PROJECT_ROOT / "data" / "certificados_prueba" / "certificado_pruebas.pem")
KEY_PATH = str(PROJECT_ROOT / "data" / "certificados_prueba" / "clave_pruebas.pem")

@pytest.fixture(autouse=True)
def setup_test_environment(tmp_path, monkeypatch):
    # Aislar base de datos
    memory_module = sys.modules["app.adapters.memory.memory"]
    test_db = tmp_path / "memory_test_user_aeat_suite.db"
    monkeypatch.setattr(memory_module, "DB_PATH", test_db)
    
    # Configurar las variables de entorno para usar los certificados de prueba reales
    monkeypatch.setenv("ALFONSO_AEAT_CERT", CERT_PATH)
    monkeypatch.setenv("ALFONSO_AEAT_KEY", KEY_PATH)
    monkeypatch.setenv("ALFONSO_API_KEY", "test_api_key_suite")
    monkeypatch.setenv("ALFONSO_BRIDGE_TOKEN", "test_bridge_token_suite")
    
    # Inicializar base de datos
    with _get_connection() as conn:
        conn.execute("DROP TABLE IF EXISTS verifactu_invoices")
        conn.execute("DROP TABLE IF EXISTS invoices")
        conn.execute("DROP TABLE IF EXISTS emails")
        conn.execute("DROP TABLE IF EXISTS user_profile")
        conn.commit()
        
        from app.adapters.memory.memory import _init_db_schema
        from app.adapters.mail_db import _init_mail_schema
        _init_db_schema(conn)
        _init_mail_schema(conn)
        VerifactuService.init_verifactu_schema()
        
        # Insertar perfil de usuario para los tests (nombres de columna correctos de user_profile)
        from app.utils.encryption import encryptor
        conn.execute("""
            INSERT INTO user_profile (user_type, razon_social, nif, cert_path, cert_password)
            VALUES (?, ?, ?, ?, ?)
        """, (
            encryptor.encrypt("autonomo"),
            encryptor.encrypt("Luis Domingo Pérez"),
            encryptor.encrypt("12345678Z"),
            encryptor.encrypt(""), # Dejamos vacío para que use las variables de entorno configuradas arriba
            encryptor.encrypt("")
        ))
        conn.commit()
        
    memory._cache.clear()
    yield

def test_verifactu_real_certs_flow():
    """
    Verifica el registro de facturas en Verifactu utilizando los certificados PEM reales
    y realiza la llamada al Sandbox de la AEAT (o su simulación de mTLS real).
    """
    assert os.path.exists(CERT_PATH), f"No se encuentra el certificado en {CERT_PATH}"
    assert os.path.exists(KEY_PATH), f"No se encuentra la clave en {KEY_PATH}"
    
    invoice = {
        "invoice_number": "SUITE-FAC-001",
        "date_of_issue": "2026-08-07",
        "issuer_nif": "12345678Z",
        "receiver_nif": "87654321A",
        "base_imponible": 1000.0,
        "iva_amount": 210.0,
        "total_amount": 1210.0
    }
    
    # Registramos e intentamos enviar al sandbox
    res = VerifactuService.register_invoice(invoice)
    assert res["status"] == "success"
    assert res["current_hash"] is not None
    
    # Comprobar si el intento de entrega a la AEAT se registró.
    # Si el sandbox está caído o inaccesible, el estado puede ser ERROR o INCIDENT,
    # pero el flujo técnico local (firmas XMLDSig, guardado del archivo) debe ser correcto.
    with _get_connection() as conn:
        row = conn.execute("SELECT * FROM verifactu_invoices WHERE invoice_number = 'SUITE-FAC-001'").fetchone()
        assert row is not None
        assert row["delivery_status"] in ("ENVIADO", "PENDIENTE", "ERROR", "INCIDENT")
        
    # Verificar que el XML generado contenga la firma XMLDSig envelopada
    xml_dir = PROJECT_ROOT / "data" / "xml_invoices"
    xml_file = xml_dir / "SUITE-FAC-001_verifactu.xml"
    assert xml_file.exists()
    
    xml_content = xml_file.read_text(encoding="utf-8")
    root = etree.fromstring(xml_content.encode("utf-8"))
    ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
    signature = root.find(".//ds:Signature", namespaces=ns)
    assert signature is not None

@pytest.mark.asyncio
async def test_tax_models_generation():
    """
    Testea las acciones tributarias del autónomo (IVA, IRPF, retenciones y fraccionamientos).
    """
    # Insertar facturas de ingresos y gastos en la base de datos contable para simular el trimestre
    income_invoice = {
        "invoice_id": "INC-001",
        "date": "2026-08-01",
        "issuer_name": "Luis Domingo Pérez",
        "issuer_nif": "12345678Z",
        "receiver_name": "Cliente de Prueba S.L.",
        "receiver_nif": "B11111111",
        "base_imponible": 5000.0,
        "iva_rate": 21.0,
        "iva_amount": 1050.0,
        "irpf_rate": 0.0,
        "irpf_amount": 0.0,
        "total_amount": 6050.0,
        "category": "income",
        "quarter": 3,
        "year": 2026
    }
    
    expense_invoice = {
        "invoice_id": "EXP-001",
        "date": "2026-08-02",
        "issuer_name": "Proveedor de Oficinas S.A.",
        "issuer_nif": "A22222222",
        "receiver_name": "Luis Domingo Pérez",
        "receiver_nif": "12345678Z",
        "base_imponible": 1000.0,
        "iva_rate": 21.0,
        "iva_amount": 210.0,
        "irpf_rate": 19.0,
        "irpf_amount": 190.0,  # Retención IRPF de alquiler
        "total_amount": 1020.0,
        "category": "expense",
        "quarter": 3,
        "year": 2026
    }
    
    TaxParserService.save_invoice_to_db(income_invoice)
    TaxParserService.save_invoice_to_db(expense_invoice)
    
    # 1. Presentación de IVA: Modelo 303
    res_303 = await generate_modelo_303_autofill_script(2026, 3)
    assert res_303["status"] == "ok"
    assert res_303["data_used"]["income_base"] == 5000.0
    assert res_303["data_used"]["expense_base"] == 1000.0
    assert "5000.0" in res_303["script"]
    
    # 2. Resumen anual de IVA: Modelo 390
    res_390 = await generate_modelo_390_summary(2026)
    assert res_390["status"] == "ok"
    assert res_390["summary"]["operaciones_interiores_devengadas_base"] == 5000.0
    assert res_390["summary"]["operaciones_interiores_deducibles_base"] == 1000.0
    
    # 3. Pago Fraccionado IRPF: Modelo 130
    res_130 = await generate_modelo_130_autofill_script(2026, 3)
    assert res_130["status"] == "ok"
    assert res_130["data_used"]["income_base"] == 5000.0
    assert res_130["data_used"]["expense_base"] == 1000.0
    # Pago fraccionado es 20% del rendimiento (6050.0 - 1020.0) * 0.20 = 1006.0
    assert res_130["data_used"]["pago_fraccionado"] == 1006.0
    
    # 4. Retenciones a profesionales/trabajadores: Modelo 111
    res_111 = await generate_modelo_111_autofill_script(2026, 3)
    assert res_111["status"] == "ok"
    assert res_111["data_used"]["retenciones_monto"] == 190.0
    
    # 5. Retenciones de alquileres: Modelo 115
    res_115 = await generate_modelo_115_autofill_script(2026, 3)
    assert res_115["status"] == "ok"
    assert res_115["data_used"]["retenciones"] == 190.0
    
    # 6. Pago fraccionado Impuesto Sociedades: Modelo 202
    res_202 = await generate_modelo_202_autofill_script(2027, 1)
    assert res_202["status"] == "ok"
    
    # 7. Declaración operaciones con terceros: Modelo 347 (> 3005.06 €)
    res_347 = await generate_modelo_347_summary(2026)
    assert res_347["status"] == "ok"
    terceros = res_347["terceros_a_declarar"]
    assert len(terceros) == 1
    assert terceros[0]["nif"] == "B11111111"  # Supera los 3005.06 €

@pytest.mark.asyncio
async def test_aeat_requirements_legal_agent():
    """
    Verifica el procesamiento de requerimientos y notificaciones de la AEAT
    delegando al agente legal Marcos.
    """
    # 1. Registrar email simulado de requerimiento fiscal de la AEAT
    email_id = create_email(
        sender="notificaciones@aeat.es",
        recipient="luis@example.com",
        subject="REQUERIMIENTO DE DOCUMENTACION IVA 2025",
        body="Se solicita la aportación de los libros registro de facturas emitidas del ejercicio fiscal 2025 en un plazo de 10 días hábiles.",
        received_at="2026-08-07 10:00:00",
        category="legal",
        importance="Alta"
    )
    assert email_id > 0
    
    # 2. Consultar a Alfonso/Marcos a través de PlannerOrchestrator
    orchestrator = PlannerOrchestrator()
    
    # Mockear OllamaClient.generate para controlar la respuesta del LLM legal
    with patch("app.adapters.llm_client.OllamaClient.generate", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = "Borrador de respuesta formal al requerimiento de IVA 2025..."
        
        user_query = "Tengo un requerimiento de la AEAT sobre el IVA de 2025 que acabo de recibir. ¿Qué debemos responder?"
        response = await orchestrator.run(
            user_message=user_query,
            session_id="suite_session_001",
            client_id="suite_client"
        )
        
        # Validamos que se derive la consulta o se procese y dé una respuesta formal
        assert response["type"] == "chat"
        assert "Borrador" in response["response"]

def test_logs_audit(caplog):
    """
    Verifica que se almacenen de forma estructurada los logs del sistema
    y que podamos auditar los mensajes de aviso y errores.
    """
    from app.utils.logger import app_logger
    
    with caplog.at_level(logging.INFO):
        app_logger.info("Auditoría de test: Alfonso ha ejecutado el módulo de AEAT correctamente.")
        
    assert any("Auditoría de test" in record.message for record in caplog.records)
