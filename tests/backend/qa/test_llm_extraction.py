import json
import pytest
from pathlib import Path
from app.domain.services.tax_parser_service import TaxParserService

CORPUS_DIR = Path(__file__).resolve().parent.parent.parent / "corpus_facturas"

def get_corpus_files():
    if not CORPUS_DIR.exists():
        return []
    return list(CORPUS_DIR.glob("*.json"))

@pytest.mark.asyncio
@pytest.mark.parametrize("corpus_file", get_corpus_files())
async def test_llm_invoice_extraction_corpus(corpus_file: Path):
    """
    Lee archivos del corpus y valida la precisión de la extracción del LLM.
    """
    with open(corpus_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    raw_text = data.get("raw_text")
    expected = data.get("expected_result")

    # Si no hay mock, esto intentará llamar a Gemini. 
    import os
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY no configurada. Saltando test de extracción real.")

    result = await TaxParserService.parse_invoice_text_with_llm(raw_text)

    # Verificar expectativas
    assert result["invoice_number"] == expected["invoice_number"]
    assert result["supplier_nif"] == expected["supplier_nif"]
    assert float(result["total_amount"]) == float(expected["total_amount"])
