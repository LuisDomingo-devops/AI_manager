from typing import Dict, Any, Tuple
from app.domain.services.local_ocr_service import LocalOCRService
from app.domain.schemas import AnonymizationSession
from app.utils.logger import app_logger

class InvoiceProcessingService:
    """
    Servicio de procesamiento de facturas con protección previa de privacidad RGPD.
    Extrae la información mediante OCR local, aplica anonimización pre-Gemini
    y reconstituye los datos contables en local.
    """

    def __init__(self):
        self.ocr_service = LocalOCRService()

    def process_invoice_document(
        self,
        file_path: str,
        session: AnonymizationSession | None = None
    ) -> Tuple[str, Dict[str, str]]:
        """
        Procesa el documento de factura extrayendo texto y anonimizando datos personales.
        Retorna el payload seguro anonimizado y el mapa de restitución.
        """
        app_logger.info("Iniciando procesamiento seguro de factura: %s", file_path)
        anon_text, mapping = self.ocr_service.extract_and_anonymize(file_path, session=session)
        return anon_text, mapping
