import pytest
from unittest.mock import patch, MagicMock
from app.domain.services.local_ocr_service import LocalOCRService
from app.utils.image_redactor import ImageRedactor

def test_local_ocr_service_extract_and_anonymize():
    ocr_service = LocalOCRService()
    fake_text = "Factura emitida por Juan Pérez con CIF B12345674 total 1.200,00 €"

    with patch.object(ocr_service, "extract_text_from_file", return_value=fake_text):
        anon_text, mapping = ocr_service.extract_and_anonymize("dummy.pdf")
        assert "[NOMBRE_1]" in anon_text
        assert "[NIF_1]" in anon_text or "[CIF_1]" in anon_text
        assert "[IMPORTE_1]" in anon_text
        assert "B12345674" not in anon_text
        cif_key = "[NIF_1]" if "[NIF_1]" in mapping else "[CIF_1]"
        assert mapping[cif_key] == "B12345674"

def test_image_redactor_applies_masks():
    redactor = ImageRedactor()
    from PIL import Image
    img = Image.new("RGB", (200, 200), color="white")
    boxes = [{"box": (10, 10, 50, 50), "confidence": 0.85, "label": "NIF"}]

    redacted_img = redactor.redact_boxes(img, boxes)
    assert redacted_img is not None
    # El píxel en el centro de la caja debe ser negro (0, 0, 0)
    pixel = redacted_img.getpixel((30, 30))
    assert pixel == (0, 0, 0)

def test_image_redactor_ignores_low_confidence():
    redactor = ImageRedactor()
    from PIL import Image
    img = Image.new("RGB", (200, 200), color="white")
    # Confianza < 60% (0.45)
    boxes = [{"box": (10, 10, 50, 50), "confidence": 0.45, "label": "NIF"}]

    redacted_img = redactor.redact_boxes(img, boxes)
    pixel = redacted_img.getpixel((30, 30))
    # Debe permanecer blanco
    assert pixel == (255, 255, 255)
