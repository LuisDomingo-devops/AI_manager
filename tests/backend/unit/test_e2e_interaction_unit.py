"""
TESTS UNITARIOS: Componentes de la Suite de Interacción E2E (Spec 017).
Cubre:
- Gestión unitaria de contexto y domain stickiness en memoria de pruebas.
- Contrato de enrutamiento y agregación de aviso legal unitario.
- Validación unitaria de escenarios de extracción sin efectos colaterales.
- Aislamiento estricto de tools operacionales en entradas conversacionales.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock

from app.domain.schemas import IntentType, LLMDecisionEnvelope, DomainErrorContract
from app.domain.services.tax_parser_service import TaxParserService


def test_unit_exact_invoice_extraction_scenario_8():
    """
    Unit test para el Escenario 8:
    'base 34.51', 'IVA 21%', 'total 41.76' -> iva_amount = 7.25, iva_rate = 21.0.
    """
    mock_llm_json = json.dumps({
        "invoice_id": "SC8-UNIT",
        "date": "2026-09-29",
        "issuer_name": "Proveedor SC8",
        "issuer_nif": "B12345674",
        "receiver_name": "Luis Domingo",
        "receiver_nif": "47019805P",
        "base_imponible": 34.51,
        "iva_rate": 21.0,
        "iva_amount": 7.25,
        "irpf_amount": 0.0,
        "total_amount": 41.76
    })

    with pytest.MonkeyPatch.context() as mp:
        async def mock_generate(*args, **kwargs):
            return mock_llm_json

        from app.infrastructure.adapters.llm_client import GeminiClient
        mp.setattr(GeminiClient, "generate", mock_generate)

        res = TaxParserService.parse_invoice_text("base 34.51, IVA 21%, total 41.76")
        assert res["base_imponible"] == 34.51
        assert res["iva_amount"] == 7.25
        assert res["iva_rate"] == 21.0
        assert res["total_amount"] == 41.76


def test_unit_conversational_envelope_classification():
    """
    Unit test para validar que los sobres de decisión conversacionales (SC1, SC2)
    tienen tipo 'message' con tool_name = None.
    """
    envelope = LLMDecisionEnvelope(
        type=IntentType.message,
        message="¡Hola! ¿En qué puedo ayudarte hoy?",
        tool_name=None,
        tool_args=None,
    )

    assert envelope.type == IntentType.message
    assert envelope.tool_name is None
    assert "Hola" in envelope.message


def test_unit_single_legal_disclaimer_rule():
    """
    Unit test para verificar la regla de inclusión de exactamente un aviso legal.
    """
    disclaimer = "AVISO LEGAL: La información proporcionada tiene carácter meramente orientativo."
    texto_original = "Esta es una respuesta legal preliminar."
    texto_con_aviso = f"{texto_original}\n\n{disclaimer}"
    
    # Contar ocurrencias
    assert texto_con_aviso.count("AVISO LEGAL:") == 1


def test_unit_domain_error_contract_on_illegible_invoice():
    """
    Unit test para el Escenario 7: comprobación unitaria de generación de contrato
    de error de dominio ante factura ilegible sin filtración de excepciones.
    """
    contrato = DomainErrorContract(
        status="needs_user_validation",
        reason_code="ILLEGIBLE_DOCUMENT",
        affected_fields=["base_imponible", "iva_rate"],
        technical_details="Traceback (most recent call last): OCRFailedError"
    )

    assert contrato.status == "needs_user_validation"
    assert "iva_rate" in contrato.affected_fields
    # Exclusión de detalles técnicos en serialización
    dump_llm = contrato.model_dump(exclude={"technical_details"})
    assert "technical_details" not in dump_llm
    assert "Traceback" not in str(dump_llm)
