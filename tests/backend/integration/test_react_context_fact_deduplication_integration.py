import pytest
from unittest.mock import MagicMock
from app.domain.planner_orchestrator import ConversationContextService
from app.infrastructure.database.memory.vector_memory import VectorMemory

@pytest.mark.asyncio
async def test_react_context_loop_preserves_single_logical_fact():
    """
    Verifica el invariante de la Sección 10 del Discovery Contract:
    same fact + multiple iterations = one logical fact.

    Al ejecutar build_context() en múltiples iteraciones ReAct consecutivas con el mismo mensaje,
    la memoria vectorial y el contexto ensamblado deben mantener exactamente 1 único hecho lógico.
    """
    vm = VectorMemory()
    mock_memory = MagicMock()
    mock_memory.get_summary.return_value = None

    context_service = ConversationContextService(memory=mock_memory, vector_memory=vm)

    session_id = "session_react_iter_01"
    client_id = "tenant_react_01"
    user_message = "recuerda que mi cliente principal es ACME Corp"

    # Simular 3 iteraciones del loop ReAct con el mismo mensaje
    for iteration in range(3):
        memory_text, style_facts, filtered_general = await context_service.build_context(
            user_message=user_message,
            session_id=session_id,
            client_id=client_id
        )

    # Invariante 1: En ChromaDB solo debe existir 1 documento para este hecho
    stored = vm.collection.get(where={"client_id": client_id})
    matching_docs = [doc for doc in stored["documents"] if "acme corp" in doc.lower()]
    assert len(matching_docs) == 1, (
        f"Infracción ReAct: multiple iterations generó {len(matching_docs)} hechos en vez de 1 único hecho lógico."
    )

    # Invariante 2: query_facts solo devuelve 1 instancia
    facts = vm.query_facts("cliente principal", limit=5, client_id=client_id)
    acme_facts = [f for f in facts if "acme corp" in f.lower()]
    assert len(acme_facts) == 1, f"query_facts devolvió duplicados en memoria: {acme_facts}"

    # Invariante 3: El texto de contexto ensamblado no repite la línea del hecho
    if memory_text:
        occurrences = memory_text.lower().count("acme corp")
        assert occurrences == 1, f"El contexto generado repite el hecho {occurrences} veces: {memory_text}"
