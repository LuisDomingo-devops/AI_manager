import pytest
from app.infrastructure.database.memory.vector_memory import VectorMemory

def test_react_context_qa_normalization_multi_facts_and_tenant_isolation():
    """
    Suite de QA para integridad de memoria semántica y deduplicación de contexto ReAct:
    1. Normalización de espacios y mayúsculas: variaciones sintácticas convergen a un único hecho lógico.
    2. Coexistencia multifactual: hechos semánticamente distintos coexisten sin sobreescribirse.
    3. Aislamiento por cliente: el mismo hecho para dos clientes distintos se almacena de forma aislada.
    """
    vm = VectorMemory()

    client_a = "tenant_qa_alpha"
    client_b = "tenant_qa_beta"

    # 1. Normalización de mayúsculas y espacios redundantes
    fact_raw_1 = "  Mi   lenguaje  FAVORITO   es   Python  "
    fact_raw_2 = "mi lenguaje favorito es python"

    id_a1 = vm.add_fact("session_qa_1", fact_raw_1, client_id=client_a)
    id_a2 = vm.add_fact("session_qa_2", fact_raw_2, client_id=client_a)

    assert id_a1 == id_a2, (
        f"Las variaciones de mayúsculas y espacios deben generar la misma identidad: {id_a1} vs {id_a2}"
    )

    docs_client_a = vm.collection.get(where={"client_id": client_a})
    matching_py = [d for d in docs_client_a["documents"] if "python" in d.lower()]
    assert len(matching_py) == 1, "Debe existir un único hecho guardado para Python en el cliente A"

    # 2. Coexistencia de hechos distintos
    fact_loc = "vivo en Valencia"
    fact_comp = "mi empresa se llama InnoTech"

    id_loc = vm.add_fact("session_qa_1", fact_loc, client_id=client_a)
    id_comp = vm.add_fact("session_qa_1", fact_comp, client_id=client_a)

    assert id_loc != id_a1
    assert id_comp != id_a1
    assert id_loc != id_comp

    docs_client_a_all = vm.collection.get(where={"client_id": client_a})
    assert len(docs_client_a_all["documents"]) == 3, (
        f"Deben coexistir exactamente 3 hechos distintos para el cliente A, encontrados: {len(docs_client_a_all['documents'])}"
    )

    # 3. Aislamiento por cliente (Client B registra el mismo hecho)
    id_b1 = vm.add_fact("session_qa_b", fact_raw_1, client_id=client_b)
    assert id_b1 != id_a1, "El fact_id debe estar aislado por client_id"

    docs_client_b = vm.collection.get(where={"client_id": client_b})
    assert len(docs_client_b["documents"]) == 1
    assert docs_client_b["metadatas"][0]["client_id"] == client_b
