"""
TESTS DE INTEGRACIÓN: Domain Error Contract & UX (Spec 016)
TDD — Estos tests deben FALLAR hasta que se complete la implementación.

Cubre:
- US1: Errores técnicos (ValidationError, etc.) no llegan al usuario final.
- US2: Workflow pausa cuando se emite needs_user_validation.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.domain.schemas import DomainErrorContract, IntentType


pytestmark = pytest.mark.asyncio


class TestShieldingValidationErrors:
    """
    US1: Comprueba que los errores técnicos no se filtran a la respuesta del usuario.
    Criterio de aceptación SC-001 y SC-002.
    """

    async def test_errores_tecnicos_no_llegan_al_usuario(self):
        """
        SC-001: Las palabras 'ValidationError', 'Pydantic', 'Traceback', 'json'
        NO deben aparecer en la respuesta final al usuario.
        """
        from app.domain.planner_orchestrator import PlannerOrchestrator
        from app.domain.schemas import DomainErrorContract

        # Crear un mock de LLM que devuelva un mensaje conversacional
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            '{"type": "message", "message": "No he podido extraer correctamente el IVA. ¿Puedes confirmarme el porcentaje?"}'
        )

        # Simular que un tool devuelve un DomainErrorContract
        domain_error = DomainErrorContract(
            status="needs_user_validation",
            reason_code="INVALID_EXTRACTED_PERCENTAGE",
            affected_fields=["iva_rate"],
            missing_values={"iva_rate": None},
            technical_details="Traceback (most recent call last):\n  ValidationError for InvoiceSchema...",
        )

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

        # Llamamos al método que transforma el DomainErrorContract en respuesta conversacional
        respuesta = orchestrator.transformar_contrato_a_respuesta(domain_error)

        # Verificación SC-001: no hay términos técnicos en la respuesta del usuario
        palabras_prohibidas = ["ValidationError", "Pydantic", "Traceback", "json", "stack trace"]
        for palabra in palabras_prohibidas:
            assert palabra.lower() not in respuesta.lower(), (
                f"La palabra técnica '{palabra}' no debe aparecer en la respuesta al usuario. "
                f"Respuesta: {respuesta}"
            )

    async def test_technical_details_nunca_en_contexto_llm(self):
        """
        SC-002: El technical_details del contrato debe registrarse en logs,
        pero nunca incluirse en el contexto enviado al LLM.
        """
        from app.domain.services.error_manager import ErrorManager

        contrato = DomainErrorContract(
            status="needs_user_validation",
            reason_code="PARSE_FAILED",
            affected_fields=["base_imponible"],
            technical_details="Traceback crítico: ValidationError at line 42",
        )

        # Obtener serialización segura para LLM (sin technical_details)
        payload_llm = ErrorManager.serializar_para_llm(contrato)

        assert "technical_details" not in payload_llm
        assert "Traceback" not in str(payload_llm)
        assert "ValidationError" not in str(payload_llm)


class TestWorkflowPausing:
    """
    US2: El workflow debe pausarse cuando se emite needs_user_validation.
    Criterio de aceptación SC-004.
    """

    async def test_orchestrator_pausa_al_recibir_domain_error_contract(self):
        """
        SC-004: Cuando el orquestador procesa un DomainErrorContract con
        status='needs_user_validation', debe devolver una respuesta de
        clarificación y NO continuar el bucle de herramientas.
        """
        from app.domain.planner_orchestrator import PlannerOrchestrator
        from app.domain.schemas import DomainErrorContract

        contrato = DomainErrorContract(
            status="needs_user_validation",
            reason_code="INVALID_EXTRACTED_PERCENTAGE",
            affected_fields=["iva_rate"],
            missing_values={"iva_rate": None},
        )

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

        # Invocar el método que maneja el contrato de dominio
        resultado = await orchestrator.manejar_domain_error_contract(
            contrato=contrato,
            session_id="sesion-123",
            client_id="cliente-1",
        )

        # Verificar que la respuesta es de tipo clarificación
        assert resultado is not None
        assert resultado.get("type") in ("chat", "clarification")
        # La respuesta SOLO menciona los affected_fields, no datos técnicos
        respuesta = resultado.get("response", "")
        assert "iva_rate" in respuesta.lower() or "iva" in respuesta.lower()
        assert "ValidationError" not in respuesta
        assert "Traceback" not in respuesta

        # El LLM no debe haber sido llamado con información técnica interna
        # (verificamos que generate fue llamado con un prompt limpio si fue llamado)
        if mock_llm.generate.called:
            for call_args in mock_llm.generate.call_args_list:
                prompt_enviado = str(call_args)
                assert "Traceback" not in prompt_enviado
                assert "ValidationError" not in prompt_enviado

    async def test_workflow_no_continua_tras_needs_user_validation(self):
        """
        FR-005: Tras emitir needs_user_validation, el sistema no debe
        procesar el siguiente documento de un lote.
        """
        from app.domain.planner_orchestrator import PlannerOrchestrator
        from app.domain.schemas import DomainErrorContract

        contrato = DomainErrorContract(
            status="needs_user_validation",
            reason_code="INVALID_EXTRACTED_PERCENTAGE",
            affected_fields=["iva_rate"],
        )

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

        resultado = await orchestrator.manejar_domain_error_contract(
            contrato=contrato,
            session_id="sesion-batch",
            client_id="cliente-1",
        )

        # El resultado debe tener un marcador que indique pausa del flujo
        assert resultado is not None
        assert resultado.get("workflow_paused") is True or resultado.get("type") in ("chat", "clarification")
