"""
Test de integración de resiliencia en infraestructura auxiliar (calendar_db y vector_memory).
Verifica que las caídas o excepciones en TaxEngine al listar eventos o al limpiar memoria
se gestionen de forma tipada sin capturas genéricas ni imports tardíos de error_logger.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock
from app.infrastructure.database import calendar_db
from app.infrastructure.database.memory import vector_memory

def test_aux_infra_no_inline_error_logger_imports():
    """Verifica que calendar_db.py y vector_memory.py no contengan imports tardíos de error_logger."""
    cal_source = (Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "database" / "calendar_db.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in cal_source, (
        "calendar_db.py aún contiene imports inline tardíos de error_logger"
    )
    vec_source = (Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "database" / "memory" / "vector_memory.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in vec_source, (
        "vector_memory.py aún contiene imports inline tardíos de error_logger"
    )

def test_calendar_list_events_tax_engine_failure_resilience():
    """Verifica que si falla el cálculo de plazos fiscales, calendar_db degrade devolviendo eventos locales."""
    with patch("app.domain.services.tax_engine.TaxEngine.get_fiscal_deadlines", side_effect=ValueError("Error calculando plazos")):
        events = calendar_db.list_events("2026-01-01", "2026-03-31")
        assert isinstance(events, list)

def test_vector_memory_clear_collection_error_resilience():
    """Verifica que vector_memory.clear() tolere errores al borrar colecciones inexistentes o corruptas."""
    mem = vector_memory
    with patch.object(mem.client, "delete_collection", side_effect=ValueError("Collection not found")):
        # No debe propagar la excepción
        mem.clear()
