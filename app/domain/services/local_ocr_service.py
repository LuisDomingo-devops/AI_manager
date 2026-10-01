import os
from typing import Tuple, Dict, Optional
from pathlib import Path
from app.utils.anonymizer import DataAnonymizer
from app.domain.schemas import AnonymizationSession
from app.utils.logger import app_logger

class LocalOCRService:
    """
    Servicio de extracción local de texto OCR para facturas y documentos (PDF / imágenes).
    Garantiza que la extracción textual se realice en la máquina del usuario
    y se anonimice antes de cualquier inferencia remota.
    """

    def __init__(self):
        self.anonymizer = DataAnonymizer()

    def extract_text_from_file(self, file_path: str) -> str:
        """
        Extrae la capa de texto nativa de un PDF con pdfplumber o ejecuta OCR con pytesseract.
        """
        path = Path(file_path)
        if not path.exists():
            return ""

        ext = path.suffix.lower()
        extracted_text = ""

        if ext == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            extracted_text += page_text + "\n"
            except Exception as e:
                app_logger.warning("Fallo al extraer texto con pdfplumber: %s", e)

        elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
            try:
                import pytesseract
                from PIL import Image
                img = Image.open(path)
                extracted_text = pytesseract.image_to_string(img, lang="spa")
            except Exception as e:
                app_logger.warning("Fallo al ejecutar OCR con pytesseract: %s", e)

        return extracted_text.strip()

    def extract_and_anonymize(
        self,
        file_path: str,
        session: Optional[AnonymizationSession] = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Extrae texto en local y aplica anonimización de datos sensibles.
        """
        raw_text = self.extract_text_from_file(file_path)
        return self.anonymizer.anonymize(raw_text, session=session)
