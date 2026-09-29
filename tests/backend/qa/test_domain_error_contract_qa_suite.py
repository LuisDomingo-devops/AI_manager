"""
QA TEST SUITE: Domain Error & UX Contract (Spec 016)
Certificación formal de los criterios de éxito:
- SC-001: Ausencia total de términos técnicos ('ValidationError', 'Pydantic', 'Traceback', 'json') en respuestas al usuario.
- SC-002: Persistencia del stack trace y detalle técnico en los logs de la aplicación.
- SC-003: Pregunta conversacional acotada estrictamente a los affected_fields.
- SC-004: Pausa inmediata del workflow (batch processing) ante needs_user_validation.
- Pruebas de límites, robustez y protección contra fugas de abstracción.
"""

import pytest
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.domain.schemas import DomainErrorContract, InvoiceSchema
from app.domain.services.error_manager import ErrorManager
from app.domain.planner_orchestrator import PlannerOrchestrator


@pytest.mark.asyncio
async def test_qa_sc001_shielding_from_technical_leakage():
    """
    SC-001: Valida que ninguna excepción técnica de bajo nivel se filtre
    a la respuesta generada por el orquestador hacia el usuario.
    """
    mock_llm = AsyncMock()
    mock_memory = MagicMock()
    mock_memory.get_metadata.return_value = None
    mock_memory.get_history.return_value = []
    mock_memory.is_testing = True
    mock_vector = MagicMock()
    mock_vector.query_facts.return_value = []

    orchestrator = PlannerOrchestrator(
        llm=mock_llm,
        memory=mock_memory,
        vector_memory=mock_vector,
    )

    contratos_con_errores = [
        DomainErrorContract(
            status="needs_user_validation",
            reason_code="INVALID_EXTRACTED_PERCENTAGE",
            affected_fields=["iva_rate"],
            technical_details="Traceback (most recent call last):\n  File 'invoice.py', line 99, in parse\n  ValidationError: 1 validation error for InvoiceSchema\niva_rate: Input should be less than or equal to 100",
        ),
        DomainErrorContract(
            status="system_error",
            reason_code="UNEXPECTED_SYSTEM_ERROR",
            affected_fields=[],
            technical_details="Traceback (most recent call last):\n  File 'pypdf/_reader.py', line 12\n  json.decoder.JSONDecodeError: Expecting value: line 1 column 1",
        ),
        DomainErrorContract(
            status="fatal_error",
            reason_code="DATABASE_CORRUPTION",
            affected_fields=[],
            technical_details="sqlite3.OperationalError: disk I/O error Traceback (most recent call last): ...",
        ),
    ]

    palabras_prohibidas = [
        "validationerror", "pydantic", "traceback", "json", "stack trace", "sqlite3", "operationalerror", "line 99"
    ]

    for contrato in contratos_con_errores:
        respuesta = orchestrator.transformar_contrato_a_respuesta(contrato)
        for palabra in palabras_prohibidas:
            assert palabra not in respuesta.lower(), (
                f"Término técnico prohibido '{palabra}' encontrado en la respuesta del usuario: '{respuesta}'"
            )


@pytest.mark.asyncio
async def test_qa_sc002_technical_details_logged_internally(caplog):
    """
    SC-002: Verifica que el stack trace técnico se registre de forma segura
    en los logs internos del sistema sin exponerse al usuario.
    """
    with caplog.at_level(logging.ERROR):
        def funcion_con_fallo_multiple():
            InvoiceSchema(
                invoice_id="INV-999",
                date="invalida",
                issuer_name="Empresa",
                issuer_nif="NIF_FALSO_123",
                receiver_name="Cliente",
                receiver_nif="NIF_FALSO_456",
                base_imponible=-50.0,
                iva_rate=999.0,
                iva_amount=-10.0,
                total_amount=-60.0,
                category="ingreso",
                quarter=1,
                year=2026,
            )

        contrato = ErrorManager.ejecutar_con_contrato(funcion_con_fallo_multiple)

        assert isinstance(contrato, DomainErrorContract)
        assert contrato.status == "needs_user_validation"
        assert len(contrato.affected_fields) >= 1
        assert contrato.technical_details is not None

        # Verificar que el logger capturó el error técnico
        assert any("ValidationError" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_qa_sc003_targeted_clarification_on_affected_fields():
    """
    SC-003: Verifica que cuando se emite needs_user_validation, la pregunta
    conversacional solicite ÚNICAMENTE los campos afectados.
    """
    orchestrator = PlannerOrchestrator(
        llm=AsyncMock(),
        memory=MagicMock(is_testing=True),
        vector_memory=MagicMock(query_facts=lambda *a, **kw: []),
    )

    contrato_iva = DomainErrorContract(
        status="needs_user_validation",
        reason_code="INVALID_IVA",
        affected_fields=["iva_rate"],
    )
    resp_iva = orchestrator.transformar_contrato_a_respuesta(contrato_iva)
    assert "iva_rate" in resp_iva.lower()
    assert "irpf" not in resp_iva.lower()
    assert "nif" not in resp_iva.lower()

    contrato_nif = DomainErrorContract(
        status="needs_user_validation",
        reason_code="INVALID_NIF",
        affected_fields=["issuer_nif"],
    )
    resp_nif = orchestrator.transformar_contrato_a_respuesta(contrato_nif)
    assert "issuer_nif" in resp_nif.lower()
    assert "iva" not in resp_nif.lower()

    contrato_multiple = DomainErrorContract(
        status="needs_user_validation",
        reason_code="INVALID_RATES",
        affected_fields=["iva_rate", "irpf_rate"],
    )
    resp_multiple = orchestrator.transformar_contrato_a_respuesta(contrato_multiple)
    assert "iva_rate" in resp_multiple.lower()
    assert "irpf_rate" in resp_multiple.lower()


@pytest.mark.asyncio
async def test_qa_sc004_workflow_pausing_in_batch_processing():
    """
    SC-004: Valida que un flujo por lotes se detenga de inmediato en el primer
    documento que requiere validación de usuario, impidiendo que los documentos
    siguientes se procesen de forma ciega.
    """
    orchestrator = PlannerOrchestrator(
        llm=AsyncMock(),
        memory=MagicMock(is_testing=True),
        vector_memory=MagicMock(query_facts=lambda *a, **kw: []),
    )

    lote_documentos = [
        {"id": "DOC-001", "es_valido": True},
        {"id": "DOC-002", "es_valido": False},  # Falla y requiere validación
        {"id": "DOC-003", "es_valido": True},   # No debe procesarse
    ]

    documentos_procesados = []
    workflow_interrumpido = False

    for doc in lote_documentos:
        if not doc["es_valido"]:
            contrato_error = DomainErrorContract(
                status="needs_user_validation",
                reason_code="CORRUPTED_DOCUMENT",
                affected_fields=["iva_rate"],
            )
            resultado = await orchestrator.manejar_domain_error_contract(contrato_error)
            if resultado.get("workflow_paused") is True:
                workflow_interrumpido = True
                break
        else:
            documentos_procesados.append(doc["id"])

    assert workflow_interrumpido is True
    assert "DOC-001" in documentos_procesados
    assert "DOC-002" not in documentos_procesados
    assert "DOC-003" not in documentos_procesados, "El documento DOC-003 no debió procesarse tras pausar el workflow"


def test_qa_serialization_security_boundary():
    """
    Verifica que la serialización de DomainErrorContract para el LLM
    elimine por diseño cualquier detalle de depuración técnica o stack trace.
    """
    contrato = DomainErrorContract(
        status="needs_user_validation",
        reason_code="SEC_CHECK",
        affected_fields=["base_imponible"],
        extracted_values={"iva": 21.0},
        missing_values={"base_imponible": None},
        technical_details="SECRET_INTERNAL_DB_PASSWORD_OR_STACKTRACE: 0xDEADBEEF at line 42",
    )

    llm_payload = ErrorManager.serializar_para_llm(contrato)

    assert "technical_details" not in llm_payload
    assert "SECRET_INTERNAL_DB_PASSWORD" not in str(llm_payload)
    assert "0xDEADBEEF" not in str(llm_payload)
    assert llm_payload["status"] == "needs_user_validation"
    assert llm_payload["reason_code"] == "SEC_CHECK"
    assert llm_payload["affected_fields"] == ["base_imponible"]
