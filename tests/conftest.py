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
os.environ["GEMINI_PROXY_URL"] = ""
os.environ["ALFONSO_API_KEY"] = "test_api_key_default"
os.environ["ALFONSO_BRIDGE_TOKEN"] = "test_bridge_token_default"
os.environ["ALFONSO_DEV_PREMIUM_BYPASS"] = ""



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

@pytest.fixture(scope="session", autouse=True)
def clean_test_databases():
    import os
    from pathlib import Path
    data_dir = Path(__file__).resolve().parent.parent / "data"
    for db_name in ["memory_test.db", "memory_test_mail.db"]:
        db_path = data_dir / db_name
        if db_path.exists():
            try:
                db_path.unlink()
            except Exception:
                pass
    yield
@pytest.fixture(autouse=True)
def reset_db_caches():
    """
    Limpia los cachés de inicialización de base de datos antes de cada test.
    Esto permite que si un test hace DROP TABLE en su teardown/setup,
    el siguiente test vuelva a ejecutar CREATE TABLE IF NOT EXISTS.
    """
    # 1. Reset memory.py _initialized_dbs
    try:
        from app.infrastructure.database.memory import memory
        memory._initialized_dbs.clear()
    except Exception:
        pass
        
    # 2. Reset module level _db_initialized flags
    try:
        from app.infrastructure.database import calendar_db, mail_db
        calendar_db._db_initialized = False
        mail_db._db_initialized = False
    except Exception:
        pass
        
    try:
        from app.infrastructure.monitoring import metrics_service
        metrics_service._db_initialized = False
    except Exception:
        pass
        
    try:
        from app.infrastructure.security import session_manager
        session_manager.SessionManager._db_initialized = False
    except Exception:
        pass
    
    yield
