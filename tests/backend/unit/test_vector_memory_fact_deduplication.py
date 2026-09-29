import pytest
from app.infrastructure.database.memory.vector_memory import VectorMemory

def test_add_fact_deduplicates_identical_facts():
    """
    Verifica que al agregar dos veces el mismo hecho para el mismo cliente:
    1. Devuelve el mismo identificador determinista del hecho.
    2. La colección de ChromaDB contiene exactamente 1 documento para ese hecho.
    3. query_facts no devuelve duplicados.
    """
    vm = VectorMemory()
    client_id = "test_tenant_dedup"
    session_id = "session_001"
    fact_text = "mi lenguaje favorito es Python"

    # Primera inserción
    id1 = vm.add_fact(session_id, fact_text, client_id=client_id)
    assert id1 != "", "La primera inserción debe devolver un ID no vacío"

    # Segunda inserción del MISMO hecho
    id2 = vm.add_fact(session_id, fact_text, client_id=client_id)
    assert id2 != "", "La segunda inserción debe devolver un ID no vacío"

    # Contrato de identidad determinista y deduplicación
    assert id1 == id2, f"Mismo hecho debe generar la misma identidad lógica: {id1} vs {id2}"

    # Comprobación física en la colección
    stored = vm.collection.get(where={"client_id": client_id})
    matching_docs = [doc for doc in stored["documents"] if doc.strip().lower() == fact_text.strip().lower()]
    assert len(matching_docs) == 1, (
        f"Se esperaba 1 único documento guardado para '{fact_text}', pero se encontraron {len(matching_docs)}"
    )

    # Comprobación de consulta semántica
    results = vm.query_facts("lenguaje favorito", limit=5, client_id=client_id)
    matching_results = [r for r in results if r.strip().lower() == fact_text.strip().lower()]
    assert len(matching_results) == 1, (
        f"query_facts debe devolver exactamente 1 ocurrencia del hecho, obtenido: {matching_results}"
    )
