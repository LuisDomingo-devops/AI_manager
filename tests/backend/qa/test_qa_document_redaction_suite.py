import pytest
from PIL import Image
from app.utils.image_redactor import ImageRedactor

def test_qa_document_redaction_blackout_verification():
    redactor = ImageRedactor()
    img = Image.new("RGB", (300, 300), color="white")

    # Coordenadas de simulación de 3 NIFs detectados
    detections = [
        {"box": (20, 20, 100, 40), "confidence": 0.95, "label": "NIF"},
        {"box": (20, 60, 150, 80), "confidence": 0.80, "label": "DIRECCION"},
        {"box": (20, 100, 80, 120), "confidence": 0.40, "label": "LOW_CONF"}, # No debe enmascararse
    ]

    redacted = redactor.redact_boxes(img, detections)

    # El área de alta confianza debe ser completamente opaca (0, 0, 0)
    for x in range(25, 95):
        for y in range(25, 35):
            assert redacted.getpixel((x, y)) == (0, 0, 0)

    # El área de baja confianza (< 60%) debe permanecer blanca
    assert redacted.getpixel((50, 110)) == (255, 255, 255)
