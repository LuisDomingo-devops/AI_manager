from typing import List, Dict, Any, Tuple
from PIL import Image, ImageDraw

class ImageRedactor:
    """
    Redactor visual para documentos e imágenes de facturas.
    Aplica máscaras negras opacas sobre las coordenadas de datos personales
    (NIFs, nombres, direcciones) cuando la confianza de detección supera el umbral del 60%.
    """
    MIN_CONFIDENCE_THRESHOLD = 0.60

    def redact_boxes(
        self,
        image: Image.Image,
        detections: List[Dict[str, Any]],
        color: Tuple[int, int, int] = (0, 0, 0)
    ) -> Image.Image:
        """
        Dibuja rectángulos opacos sobre las coordenadas especificadas en 'box'
        para todas aquellas detecciones con confianza >= 0.60.
        """
        if not image or not detections:
            return image

        redacted = image.copy()
        draw = ImageDraw.Draw(redacted)

        for det in detections:
            confidence = det.get("confidence", 1.0)
            if confidence >= self.MIN_CONFIDENCE_THRESHOLD:
                box = det.get("box")
                if box and len(box) == 4:
                    draw.rectangle(box, fill=color)

        return redacted
