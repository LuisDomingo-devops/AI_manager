import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.local_ocr_service import LocalOCRService

def test_document_masking_pipeline_integration():
    service = LocalOCRService()
    text = "Factura de suministro con NIF 12345678Z e importe 99,99 €."

    with patch.object(service, "extract_text_from_file", return_value=text):
        anon_text, mapping = service.extract_and_anonymize("factura.pdf")
        assert "[NIF_1]" in anon_text
        assert "[IMPORTE_1]" in anon_text
        assert "12345678Z" not in anon_text
