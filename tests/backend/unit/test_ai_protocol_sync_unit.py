"""
Test Unitario para Sincronización del Protocolo IA y Deduplicación de Tools (User Story 7).
Valida que el parser JSON robusto procese las respuestas del LLM sin ProtocolError y que las tools no se dupliquen.
"""

import pytest
from app.domain.services.llm_parser import LlmParser
from app.domain.services.prompt_generator import PromptGenerator


def test_extract_json_robust_handles_various_formats():
    """Valida la extracción de JSON ante respuestas con markdown, texto previo y saltos de línea."""
    parser = LlmParser()
    
    # Formato 1: Bloque de código con ```json
    raw_1 = 'Claro, aquí tienes la factura:\n```json\n{"action": "emit_invoice", "params": {"total": 1210.0}}\n```\n¿Deseas confirmarla?'
    data_1 = parser.extract_json_robust(raw_1)
    assert data_1["action"] == "emit_invoice"
    assert data_1["params"]["total"] == 1210.0
    
    # Formato 2: JSON plano con espacios y texto alrededor
    raw_2 = 'Por supuesto: {"action": "query_tax", "params": {"model": "303"}} Gracias.'
    data_2 = parser.extract_json_robust(raw_2)
    assert data_2["action"] == "query_tax"
    assert data_2["params"]["model"] == "303"
    
    # Formato 3: JSON sin markdown y múltiples líneas
    raw_3 = '{\n  "action": "reconcile_bank",\n  "params": {\n    "entry_id": 101\n  }\n}'
    data_3 = parser.extract_json_robust(raw_3)
    assert data_3["action"] == "reconcile_bank"


def test_tools_deduplication_in_prompt_generator():
    """Valida que el catálogo de herramientas no contenga herramientas repetidas en el prompt final."""
    generator = PromptGenerator()
    
    # Simular lista de herramientas con duplicados accidentales
    tools = [
        {"name": "emit_invoice", "description": "Emite factura Veri*Factu"},
        {"name": "reconcile_bank", "description": "Concilia banco"},
        {"name": "emit_invoice", "description": "Emite factura Veri*Factu (duplicada)"}
    ]
    
    rendered_prompt = generator.format_tools_prompt(tools)
    # Debe aparecer exactamente una vez 'emit_invoice'
    assert rendered_prompt.count("emit_invoice") == 1
    assert "reconcile_bank" in rendered_prompt
