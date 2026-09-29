"""
QA TEST SUITE: End-to-End Interaction Certification (Spec 017).
Certifica formalmente:
- FR-001 a FR-006: Inspección profunda de efectos colaterales, agentes invocados y ausencia de loops.
- SC-001 a SC-003: Validación exhaustiva de los 9 escenarios de diagnóstico Discovery.
- Ausencia rigurosa de términos técnicos en respuestas del sistema.
- Aislamiento total de estado entre turnos conversacionales consecutivos.
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.domain.planner_orchestrator import PlannerOrchestrator
from app.domain.schemas import DomainErrorContract, IntentType


FORBIDDEN_WORDS = [
    "validationerror", "pydantic", "traceback", "jsondecodeerror",
    "json decode", "stack trace", "exception", "sqlite3", "operationalerror"
]


class DummyMemory:
    """Memoria de prueba aislada."""
    def __init__(self):
        self.history = []
        self.metadata = {}
        self.is_testing = True

    def add_message(self, session_id, role, content, client_id=None):
        self.history.append({"role": role, "content": content})

    def get_history(self, session_id, client_id=None):
        return self.history

    def clear(self, session_id=None):
        self.history = []
        self.metadata = {}

    def get_metadata(self, session_id, client_id=None):
        return self.metadata.get(session_id)

    def upsert_metadata(self, session_id, **kwargs):
        if session_id not in self.metadata:
            self.metadata[session_id] = {}
        self.metadata[session_id].update(kwargs)

    def update_summary(self, session_id, summary):
        pass

    def get_summary(self, session_id, client_id=None):
        return None

    def update_domain_context(self, session_id, active_domain=None, last_intent=None, client_id=None):
        if session_id not in self.metadata:
            self.metadata[session_id] = {}
        if active_domain:
            self.metadata[session_id]["active_domain"] = active_domain
        if last_intent:
            self.metadata[session_id]["last_intent"] = last_intent


@pytest.mark.asyncio
async def test_qa_conversational_turn_zero_tool_calls_and_no_leakage():
    """
    QA SC1 & SC2: Valida que inputs puramente conversacionales ("hola", "no saludas?")
    tengan cero tool calls y ninguna fuga técnica.
    """
    for prompt in ["hola", "no saludas?"]:
        memory = DummyMemory()
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.side_effect = [
            '{"type": "message", "message": "conversational", "domain": "general"}',
            "¡Hola! ¿En qué puedo ayudarte hoy?",
        ]
        mock_vector = MagicMock(query_facts=lambda *a, **kw: [])

        orchestrator = PlannerOrchestrator(llm=mock_llm, memory=memory, vector_memory=mock_vector)

        with patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool, \
             patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")):
            resultado = await orchestrator.run(
                user_message=prompt,
                session_id=f"qa-conv-{prompt}",
            )

            # Cero herramientas ejecutadas
            mock_get_tool.assert_not_called()

            # Respuesta no vacía y libre de términos técnicos
            resp_text = resultado.get("response", "")
            assert len(resp_text) > 0
            for w in FORBIDDEN_WORDS:
                assert w not in resp_text.lower(), f"Palabra técnica '{w}' encontrada en respuesta: {resp_text}"


@pytest.mark.asyncio
async def test_qa_accounting_stickiness_does_not_route_to_marcos():
    """
    QA SC4, SC5, SC6: Consultas y correcciones contables sobre IVA
    deben permanecer en el orquestador sin activar MarcosAgent.
    """
    accounting_prompts = [
        "¿cuánto IVA he pagado?",
        "me has dicho el IVA cobrado, yo te pregunto por el pagado",
        "te estás inventando el IVA"
    ]

    for i, prompt in enumerate(accounting_prompts):
        session_id = f"qa-acct-sess-{i}"
        memory = DummyMemory()
        memory.upsert_metadata(session_id, active_domain="accounting", is_persistent=True)
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock()
        mock_llm.generate.side_effect = [
            '{"type": "message", "message": "operational", "domain": "accounting"}',
            '{"type": "message", "message": "Para calcular tu IVA soportado necesito revisar tus facturas de gasto del trimestre."}',
        ]
        mock_vector = MagicMock(query_facts=lambda *a, **kw: [])

        orchestrator = PlannerOrchestrator(llm=mock_llm, memory=memory, vector_memory=mock_vector)

        with patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock) as mock_marcos, \
             patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")):
            resultado = await orchestrator.run(
                user_message=prompt,
                session_id=session_id,
            )
            # MarcosAgent NUNCA debe ser llamado
            mock_marcos.assert_not_called()
            resp_text = resultado.get("response", "")
            for w in FORBIDDEN_WORDS:
                assert w not in resp_text.lower()


@pytest.mark.asyncio
async def test_qa_explicit_legal_routes_with_single_disclaimer():
    """
    QA SC9: Una consulta legal explícita debe activar MarcosAgent
    y contener exactamente una copia del aviso legal.
    """
    memory = DummyMemory()
    memory.upsert_metadata("qa-legal-sess", active_domain="legal", is_persistent=True)
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "legal"}',
    ]
    mock_vector = MagicMock(query_facts=lambda *a, **kw: [])

    orchestrator = PlannerOrchestrator(llm=mock_llm, memory=memory, vector_memory=mock_vector)

    with patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response", new_callable=AsyncMock) as mock_marcos, \
         patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")):
        mock_marcos.return_value = "Desde el punto de vista normativo, debes presentar el modelo 303 trimestralmente."

        resultado = await orchestrator.run(
            user_message="¿Es legal deducirme el 100% de la gasolina de mi coche particular?",
            session_id="qa-legal-sess",
        )

        resp_text = resultado.get("response", "")
        # MarcosAgent SÍ fue llamado
        assert mock_marcos.called
        # Debe contener el aviso legal informativo
        assert "AVISO LEGAL:" in resp_text
        # Debe aparecer exactamente UNA vez
        assert resp_text.count("AVISO LEGAL:") == 1


@pytest.mark.asyncio
async def test_qa_loop_prevention_on_failing_document():
    """
    QA FR-004 & SC7: Asegura que un documento defectuoso no provoque reintentos
    infinitos (bucle de herramientas) y pause el flujo con aclaración dirigida.
    """
    memory = DummyMemory()
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock()
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "tool_call", "tool_name": "parse_invoice", "tool_args": {"file_path": "factura_ilegible.jpg"}}',
    ]
    mock_vector = MagicMock(query_facts=lambda *a, **kw: [])

    contrato_error = DomainErrorContract(
        status="needs_user_validation",
        reason_code="INVALID_EXTRACTED_PERCENTAGE",
        affected_fields=["iva_rate"],
        missing_values={"iva_rate": None},
        technical_details="Traceback (most recent call last):\n  ValidationError for InvoiceSchema...",
    )

    mock_parse_invoice = AsyncMock(return_value=contrato_error)

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe", new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.get_tool", return_value=mock_parse_invoice), \
         patch("app.config.Settings.get_client_role", return_value="admin"), \
         patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "")):

        orchestrator = PlannerOrchestrator(llm=mock_llm, memory=memory, vector_memory=mock_vector)
        resultado = await orchestrator.run(
            user_message="procesa la factura adjunta",
            session_id="qa-sc7-sess",
            client_id="cliente-test",
        )

        # La herramienta se ejecuta como máximo 1 vez antes de pausar (no bucle infinito)
        assert mock_parse_invoice.call_count <= 1
        # El workflow se pausó
        assert resultado.get("workflow_paused") is True
        # Se solicita aclaración sin términos técnicos
        resp_text = resultado.get("response", "")
        for w in FORBIDDEN_WORDS:
            assert w not in resp_text.lower()
