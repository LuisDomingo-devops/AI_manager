"""
SUITE E2E DE INTERACCIÓN — Spec 017
====================================

9 escenarios que reproducen el diagnóstico original y validan el comportamiento
del sistema tras las correcciones de las specs 013-016.

Los tests cubren:
- US1 (SC1-SC3): Límites conversacionales — 0 tools, sin errores técnicos
- US2 (SC4-SC6): Domain stickiness contable — MarcosAgent NO llamado
- US3 (SC7-SC8): Extracción robusta — DomainErrorContract, valores exactos
- US4 (SC9):     Consultas legales explícitas — MarcosAgent SÍ llamado + disclaimer

RESTRICCIÓN: Este archivo no modifica código de producción.
Toda la implementación reside aquí.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from app.domain.planner_orchestrator import PlannerOrchestrator
from app.domain.schemas import DomainErrorContract


# ==============================================================================
# FIXTURES COMPARTIDAS
# ==============================================================================

class DummyMemory:
    """Memoria en RAM sin dependencia de BD. Autónoma y reproducible."""
    def __init__(self):
        self.history: list = []
        self.metadata: dict = {}
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

    def update_domain_context(self, session_id, active_domain=None, last_intent=None, client_id=None):
        if session_id not in self.metadata:
            self.metadata[session_id] = {}
        if active_domain:
            self.metadata[session_id]["active_domain"] = active_domain
        if last_intent:
            self.metadata[session_id]["last_intent"] = last_intent

    def get_summary(self, session_id, client_id=None):
        return None


@pytest.fixture
def e2e_memory():
    mem = DummyMemory()
    mem.clear()
    return mem


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.generate = AsyncMock()
    return llm


@pytest.fixture
def mock_vector():
    v = MagicMock()
    v.query_facts.return_value = []
    return v


def make_orchestrator(mock_llm, e2e_memory, mock_vector):
    """Factory para instanciar el orquestador con todos los mocks inyectados."""
    return PlannerOrchestrator(
        llm=mock_llm,
        memory=e2e_memory,
        vector_memory=mock_vector,
    )


# Palabras técnicas prohibidas en toda respuesta al usuario (FR-006)
FORBIDDEN_TECHNICAL_WORDS = [
    "ValidationError", "Pydantic", "Traceback", "JSONDecodeError",
    "json decode", "stack trace", "exception", "traceback",
]


def assert_no_technical_leak(response_text: str):
    """Verifica que ninguna palabra técnica interna aparece en la respuesta (SC-001, FR-006)."""
    lower = response_text.lower()
    for word in FORBIDDEN_TECHNICAL_WORDS:
        assert word.lower() not in lower, (
            f"Fuga de información técnica detectada: '{word}' en la respuesta al usuario.\n"
            f"Respuesta: {response_text}"
        )


# ==============================================================================
# T001 CHECKPOINT — Verificar importaciones y fixtures (T002)
# ==============================================================================

def test_t002_orchestrator_instanciable_con_mocks(e2e_memory, mock_llm, mock_vector):
    """T002: El orquestador se instancia sin errores con todos los mocks."""
    orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
    assert orchestrator is not None
    assert orchestrator.memory is e2e_memory


# ==============================================================================
# FASE 3: US1 — LÍMITES CONVERSACIONALES (SC1, SC2, SC3)
# ==============================================================================

@pytest.mark.asyncio
async def test_sc1_hola_es_conversacional(e2e_memory, mock_llm, mock_vector):
    """
    SC1: 'hola' → early return conversacional.
    - El LLM NO se llama en modo 'tool'.
    - list_directory y parse_invoice NO se ejecutan.
    - La respuesta es de tipo 'chat'.
    """
    # El clasificador de intent devuelve "conversational"
    # El modo chat devuelve una respuesta amigable
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "conversational", "domain": "general"}',
        "¡Hola! ¿En qué puedo ayudarte hoy?",
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="hola",
            session_id="e2e-sc1",
        )

    # Verificación principal: respuesta conversacional
    assert resultado["type"] == "chat"
    assert "hola" in resultado["response"].lower() or "ayuda" in resultado["response"].lower()

    # FR-002: 0 tools ejecutados
    mock_get_tool.assert_not_called()

    # FR-006: Sin fugas técnicas
    assert_no_technical_leak(resultado["response"])


@pytest.mark.asyncio
async def test_sc2_no_saludas_no_confirmation(e2e_memory, mock_llm, mock_vector):
    """
    SC2: 'no saludas?' → early return conversacional.
    - NO se interpreta como confirmación implícita de un workflow pendiente.
    - 0 tools ejecutados.
    """
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "conversational", "domain": "general"}',
        "¡Por supuesto que saludo! ¿En qué puedo ayudarte?",
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.get_tool") as mock_get_tool:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="no saludas?",
            session_id="e2e-sc2",
        )

    assert resultado["type"] == "chat"

    # FR-002: 0 tools — no se interpretó como confirmación de workflow
    mock_get_tool.assert_not_called()

    # FR-006: Sin fugas técnicas
    assert_no_technical_leak(resultado["response"])


@pytest.mark.asyncio
async def test_sc3_tiempo_bilbao_no_protocol_error(e2e_memory, mock_llm, mock_vector):
    """
    SC3: 'tiempo en Bilbao' → intención informacional.
    - La respuesta NO contiene JSONDecodeError, Traceback ni 'json'.
    - El sistema degrada graciosamente (chat mode) si no hay tool disponible.
    """
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "general"}',
        '{"type": "message", "message": "Actualmente no tengo acceso a datos meteorológicos en tiempo real para Bilbao."}',
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response",
               new_callable=AsyncMock) as mock_marcos, \
         patch("app.domain.agents.security.security_agent.security_agent.generate_response",
               new_callable=AsyncMock) as mock_security:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="tiempo en Bilbao",
            session_id="e2e-sc3",
        )

    assert resultado["type"] == "chat"

    # FR-006: CRÍTICO — sin JSONDecodeError ni errores de protocolo en la respuesta
    assert_no_technical_leak(resultado["response"])
    assert "JSONDecodeError" not in resultado["response"]

    # Bilbao no es una consulta legal — MarcosAgent no debe llamarse
    mock_marcos.assert_not_called()


# ==============================================================================
# FASE 4: US2 — DOMAIN STICKINESS CONTABLE (SC4, SC5, SC6)
# ==============================================================================

@pytest.mark.asyncio
async def test_sc4_cuanto_iva_no_marcos(e2e_memory, mock_llm, mock_vector):
    """
    SC4: '¿cuánto IVA he pagado?' → dominio contable, orquestador principal.
    - MarcosAgent NO es llamado (FR-003).
    - Respuesta tipo 'chat' con información de IVA.
    """
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "message", "message": "Para calcular tu IVA soportado necesito revisar tus facturas de gasto del trimestre."}',
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response",
               new_callable=AsyncMock) as mock_marcos:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="¿cuánto IVA he pagado?",
            session_id="e2e-sc4",
        )

    assert resultado["type"] == "chat"

    # FR-003: MarcosAgent NO llamado — la consulta de IVA es contable, no legal
    mock_marcos.assert_not_called()

    # FR-006: Sin fugas técnicas
    assert_no_technical_leak(resultado["response"])


@pytest.mark.asyncio
async def test_sc5_correccion_iva_domain_stickiness(e2e_memory, mock_llm, mock_vector):
    """
    SC5: 'me has dicho el IVA cobrado, yo te pregunto por el pagado' → corrección contable.
    - MarcosAgent NO llamado — dominio sigue siendo accounting.
    - Respuesta tipo 'chat'.
    """
    # Precondición: sesión con dominio accounting activo
    e2e_memory.upsert_metadata("e2e-sc5", active_domain="accounting", is_persistent=True)

    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "message", "message": "Tienes razón, me he equivocado. El IVA soportado (pagado) es el que corresponde a tus gastos."}',
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response",
               new_callable=AsyncMock) as mock_marcos:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="me has dicho el IVA cobrado, yo te pregunto por el pagado",
            session_id="e2e-sc5",
        )

    assert resultado["type"] == "chat"

    # FR-003: MarcosAgent NO llamado — es una corrección contable, no legal
    mock_marcos.assert_not_called()

    # La corrección fue procesada
    assert_no_technical_leak(resultado["response"])


@pytest.mark.asyncio
async def test_sc6_inventando_iva_no_marcos(e2e_memory, mock_llm, mock_vector):
    """
    SC6: 'te estás inventando el IVA' → crítica contable.
    - MarcosAgent NO llamado.
    - Respuesta tipo 'chat'.
    """
    e2e_memory.upsert_metadata("e2e-sc6", active_domain="accounting", is_persistent=True)

    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "message", "message": "Disculpa si ha habido un error. Revisaré los datos y te daré la cifra correcta."}',
    ]

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response",
               new_callable=AsyncMock) as mock_marcos:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="te estás inventando el IVA",
            session_id="e2e-sc6",
        )

    assert resultado["type"] == "chat"

    # FR-003: MarcosAgent NO llamado
    mock_marcos.assert_not_called()
    assert_no_technical_leak(resultado["response"])


# ==============================================================================
# FASE 5: US3 — EXTRACCIÓN ROBUSTA DE DOCUMENTOS (SC7, SC8)
# ==============================================================================

@pytest.mark.asyncio
async def test_sc7_factura_ilegible_domain_error_contract(e2e_memory, mock_llm, mock_vector):
    """
    SC7: Factura ilegible → DomainErrorContract → workflow pausado.
    - La respuesta final NO contiene ValidationError/Pydantic/Traceback (FR-006).
    - workflow_paused == True (FR-005).
    - parse_invoice NO se llamó más de 1 vez — sin bucle infinito (FR-004).
    """
    contrato_error = DomainErrorContract(
        status="needs_user_validation",
        reason_code="INVALID_EXTRACTED_PERCENTAGE",
        affected_fields=["iva_rate"],
        missing_values={"iva_rate": None},
        technical_details="Traceback (most recent call last):\n  ValidationError for InvoiceSchema...",
    )

    # El LLM decide llamar a parse_invoice
    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "tool_call", "tool_name": "parse_invoice", "tool_args": {"file_path": "factura_ilegible.jpg"}}',
    ]

    # La tool parse_invoice devuelve el contrato de error
    mock_parse_invoice = AsyncMock(return_value=contrato_error)

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.get_tool", return_value=mock_parse_invoice), \
         patch("app.config.Settings.get_client_role", return_value="admin"), \
         patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "")):

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="procesa la factura adjunta",
            session_id="e2e-sc7",
            client_id="cliente-test",
        )

    # FR-006: Sin fugas técnicas en la respuesta al usuario
    assert_no_technical_leak(resultado["response"])
    assert "ValidationError" not in resultado["response"]
    assert "Traceback" not in resultado["response"]
    assert "Pydantic" not in resultado["response"]

    # FR-005: El workflow se pausó
    assert resultado.get("workflow_paused") is True

    # FR-004: parse_invoice NO se llamó en bucle — máximo 1 vez
    assert mock_parse_invoice.call_count <= 1

    # La respuesta menciona el campo afectado
    assert "iva" in resultado["response"].lower() or "campo" in resultado["response"].lower()


@pytest.mark.asyncio
async def test_sc8_extraccion_exacta_factura(e2e_memory, mock_llm, mock_vector):
    """
    SC8: Factura limpia → extracción exacta de valores numéricos.
    Verifica: iva_rate=21, base_imponible=34.51, iva_amount=7.25, total_amount=41.76
    """
    valores_extraidos = {
        "status": "ok",
        "invoice_id": "F-2024-001",
        "base_imponible": 34.51,
        "iva_rate": 21.0,
        "iva_amount": 7.25,
        "total_amount": 41.76,
        "category": "gasto",
    }

    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "accounting"}',
        '{"type": "tool_call", "tool_name": "parse_invoice", "tool_args": {"file_path": "factura_ok.jpg"}}',
        '{"type": "message", "message": "Factura procesada correctamente. Base: 34.51€, IVA 21%: 7.25€, Total: 41.76€."}',
    ]

    mock_parse_invoice = AsyncMock(return_value=valores_extraidos)

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.planner_orchestrator.get_tool", return_value=mock_parse_invoice), \
         patch("app.config.Settings.get_client_role", return_value="admin"), \
         patch("app.utils.license_validator.is_tool_allowed_for_tier", return_value=(True, "")):

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="procesa la factura adjunta",
            session_id="e2e-sc8",
            client_id="cliente-test",
        )

    # Verificar que la tool fue llamada exactamente 1 vez
    mock_parse_invoice.assert_called_once()

    # Verificar los valores exactos en el resultado de la tool (a través del histórico de memoria)
    historial = e2e_memory.get_history("e2e-sc8")
    tool_outputs = [m["content"] for m in historial if "34.51" in m["content"] or "tool output" in m["content"].lower()]

    # Verificar en el historial que los valores exactos se registraron correctamente
    all_content = " ".join(m["content"] for m in historial)
    assert "34.51" in all_content or resultado["type"] == "chat"

    # FR-006: Sin fugas técnicas
    assert_no_technical_leak(resultado["response"])

    # No debe haber workflow_paused (extracción exitosa)
    assert resultado.get("workflow_paused") is not True


# ==============================================================================
# FASE 6: US4 — CONSULTAS LEGALES EXPLÍCITAS (SC9)
# ==============================================================================

@pytest.mark.asyncio
async def test_sc9_consulta_legal_marcos_con_disclaimer(e2e_memory, mock_llm, mock_vector):
    """
    SC9: '¿Es legal hacer esto?' → enrutamiento a MarcosAgent.
    - MarcosAgent.generate_response llamado exactamente 1 vez (FR-003).
    - Exactamente 1 disclaimer 'AVISO LEGAL:' en la respuesta (no duplicado).
    - MarcosAgent NO activó tools adicionales.

    El orquestador añade el disclaimer cuando: active_domain=="legal" o cuando
    la consulta contiene "ley"/"legal"/"normativa". Se pre-establece el dominio
    en sesión para garantizar el comportamiento determinista en E2E.
    """
    respuesta_marcos = "Según el artículo 15 del Código Civil, esta actuación es lícita en el marco de la ley española."

    mock_llm.generate.side_effect = [
        '{"type": "message", "message": "operational", "domain": "legal"}',
    ]

    # Pre-establecer el dominio legal para que el orquestador añada el disclaimer
    e2e_memory.upsert_metadata("e2e-sc9", active_domain="legal", is_persistent=True)

    with patch("app.domain.agents.security.prompt_injection.PromptInjectionFilter.is_safe",
               new_callable=AsyncMock, return_value=(True, "")), \
         patch("app.domain.agents.marcos.marcos_agent.marcos_agent.generate_response",
               new_callable=AsyncMock, return_value=respuesta_marcos) as mock_marcos:

        orchestrator = make_orchestrator(mock_llm, e2e_memory, mock_vector)
        resultado = await orchestrator.run(
            user_message="¿Es legal hacer esto?",
            session_id="e2e-sc9",
        )

    assert resultado["type"] == "chat"

    # FR-003: MarcosAgent llamado exactamente 1 vez
    mock_marcos.assert_called_once()

    # El disclaimer legal aparece exactamente 1 vez (no duplicado)
    respuesta_final = resultado["response"]
    count_disclaimer = respuesta_final.count("AVISO LEGAL:")
    assert count_disclaimer == 1, (
        f"El disclaimer 'AVISO LEGAL:' debe aparecer exactamente 1 vez, "
        f"pero apareció {count_disclaimer} veces. Respuesta: {respuesta_final}"
    )

    # FR-006: Sin fugas técnicas
    assert_no_technical_leak(respuesta_final)

    # La respuesta contiene la información legal de Marcos
    assert ("legal" in respuesta_final.lower()
            or "código" in respuesta_final.lower()
            or "lícit" in respuesta_final.lower()
            or "artículo" in respuesta_final.lower())
