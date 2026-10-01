from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Tuple, Optional
from app.domain.schemas import AnonymizationSession

class IDataAnonymizerService(ABC):
    """
    Contrato de interfaz para el servicio de anonimización y privacidad pre-Gemini.
    Garantiza el cumplimiento estricto del RGPD / LOPDGDD.
    """

    @abstractmethod
    def anonymize_text(self, text: str, session: Optional[AnonymizationSession] = None) -> Tuple[str, AnonymizationSession]:
        """
        Analiza el texto de entrada, detecta entidades sensibles con validación algorítmica,
        reemplaza los valores por tokens sintéticos únicos y actualiza la sesión.
        """
        pass

    @abstractmethod
    def detokenize_text(self, text: str, token_to_value_map: Dict[str, str]) -> str:
        """
        Reemplaza los tokens sintéticos presentes en la respuesta por sus valores originales.
        Garantiza que cualquier token inexistente se mantenga intacto sin lanzar excepción.
        """
        pass

    @abstractmethod
    async def detokenize_stream(
        self,
        stream_generator: AsyncGenerator[str, None],
        token_to_value_map: Dict[str, str]
    ) -> AsyncGenerator[str, None]:
        """
        Envuelve un generador de SSE, aplicando un buffer de delimitadores de tokens
        para resolver tokens fragmentados entre chunks y emitir texto reconstituido en tiempo real.
        """
        pass

    @abstractmethod
    def mask_document_text(self, raw_ocr_text: str) -> Tuple[str, AnonymizationSession]:
        """
        Anonimiza texto plano extraído de un documento escaneado u OCR local
        antes de su envío a inferencia LLM para contabilización.
        """
        pass
