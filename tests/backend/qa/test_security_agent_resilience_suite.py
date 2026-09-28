"""
Suite de QA de resiliencia y ciberseguridad para el agente de seguridad y cliente LLM.
Valida que las inspecciones de payloads malformados y prompts de sistema no contengan
patrones defectuosos de AI-slop ni imports inline de error_logger.
"""

import inspect
from pathlib import Path
import pytest
from unittest.mock import patch
import app.domain.agents.security.security_agent as sec_module
from app.domain.agents.security.security_agent import CyberSecurityAgent
from app.infrastructure.adapters import llm_client
from app.infrastructure.adapters.llm_client import get_system_prompt

def test_security_and_llm_no_inline_error_logger_imports():
    """Verifica que security_agent.py y llm_client.py no contengan imports tardíos de error_logger."""
    sec_source = (Path(__file__).resolve().parents[3] / "app" / "domain" / "agents" / "security" / "security_agent.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in sec_source, (
        "security_agent.py aún contiene imports inline tardíos de error_logger"
    )
    llm_source = (Path(__file__).resolve().parents[3] / "app" / "infrastructure" / "adapters" / "llm_client.py").read_text(encoding="utf-8")
    assert '    from app.utils.logger import error_logger' not in llm_source, (
        "llm_client.py aún contiene imports inline tardíos de error_logger"
    )

def test_security_agent_corrupted_customization_body():
    """Verifica que inspect_request analice de forma segura payloads corruptos sin excepción no controlada."""
    agent = CyberSecurityAgent()
    corrupt_body = "{invalid_json_payload: not_quoted"
    # Debe procesar sin romperse ante JSONDecodeError
    is_blocked = agent.inspect_request("192.168.1.50", "/api/customization/settings", "POST", {}, corrupt_body)
    assert isinstance(is_blocked, bool)

def test_llm_client_prompt_generation_resilience_on_context_error():
    """Verifica que get_system_prompt degrade con gracia si falla get_client_context_str."""
    with patch("app.infrastructure.adapters.llm_client.get_client_context_str", side_effect=KeyError("Missing client ctx")):
        prompt = get_system_prompt("chat", "client_unknown")
        assert prompt is not None
        assert len(prompt) > 0
