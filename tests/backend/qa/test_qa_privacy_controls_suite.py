import pytest
from app.config import settings

def test_qa_anonymize_llm_calls_cannot_be_disabled_in_prod():
    # La configuración ANONYMIZE_LLM_CALLS debe ser True por defecto
    assert settings.ANONYMIZE_LLM_CALLS is True
