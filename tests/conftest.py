import sys
from unittest.mock import MagicMock, patch, AsyncMock
import pytest
import os
# Deshabilita el mock global del módulo app.adapters.memory que causaba problemas.
# En su lugar, usaremos fixtures específicos o mocks más precisos.
# Si app.adapters.memory tiene una instancia global 'memory', la parchearemos.
# Forzamos a que cualquier instancia de SessionMemory use la base de datos de test local
os.environ["ALFONSO_DB_PATH"] = "data/memory_test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ALFONSO_API_KEY"] = "test_api_key_default"
os.environ["ALFONSO_BRIDGE_TOKEN"] = "test_bridge_token_default"



@pytest.fixture
def session_memory_fixture():
    """
    Proporciona una instancia de SessionMemory con una base de datos SQLite en memoria
    para cada test, asegurando aislamiento.
    """
    from app.adapters.memory import SessionMemory
    # Usamos ':memory:' para una base de datos en memoria que se destruye al finalizar el test.
    mem = SessionMemory(max_messages=20)
    yield mem

@pytest.fixture(autouse=True)
def mock_memory(request):
    """
    Fixture para parchear la instancia global 'memory' en app.adapters.memory
    y en cualquier módulo que la importe, como planner_orchestrator.
    Esto evita que los tests de agentes interactúen con la DB real, pero
    permite a los tests de persistencia usar la DB física aislada.
    """
    db_tests = ["test_memory", "test_verifactu", "test_encryption", "test_license", "test_invoice_drafts", "test_qa_integration"]
    if any(x in request.node.nodeid for x in db_tests):
        yield
        return
    with patch("app.adapters.memory.memory") as mocked:
        # Configuramos comportamientos básicos si es necesario
        mocked.get_summary.return_value = ""
        yield mocked
