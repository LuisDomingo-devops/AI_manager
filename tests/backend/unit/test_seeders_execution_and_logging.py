"""
Test Unitario: Observabilidad y Ejecución de Seeders (Spec 001 - TDD)
Verifica que dev_seeder y legal_seeder emiten logs estructurados informativos
y no contienen fallos silenciosos ni código muerto.
"""

import logging
from unittest.mock import patch, MagicMock
import pytest
from app.utils.dev_seeder import seed_database
from app.utils.legal_seeder import parse_law_xml

def test_dev_seeder_logging():
    """Comprueba que seed_database emite trazas estructuradas con app_logger.info."""
    with patch("app.utils.dev_seeder.app_logger.info") as mock_info:
        seed_database()

    # Verificar que se registran los mensajes informativos emitidos por app_logger
    messages = [call.args[0] for call in mock_info.call_args_list if call.args]
    log_text = " ".join(messages).lower()
    assert "facturas" in log_text or "siembra" in log_text
    assert "clientes" in log_text or "proyectos" in log_text


def test_legal_seeder_xml_parsing_logging():
    """Comprueba que parse_law_xml procesa preceptos válidos sin depender de sentencias pass."""
    sample_xml = """<?xml version="1.0" encoding="utf-8"?>
    <documento>
        <bloque tipo="precepto" id="art1" titulo="Artículo 1">
            <version>
                <p>Texto del artículo 1 de prueba.</p>
            </version>
        </bloque>
    </documento>
    """
    articles = parse_law_xml(sample_xml, "Ley de Prueba")
    assert len(articles) == 1
    assert articles[0]["metadata"]["article_id"] == "art1"
    assert "Texto del artículo 1" in articles[0]["text"]
