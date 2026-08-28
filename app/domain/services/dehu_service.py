"""
DEHÚ SERVICE — Servicio para procesar y analizar las notificaciones electrónicas de la DEHú.

¿QUÉ HACE?
1. Extrae el texto plano de los archivos PDF descargados de la DEHú (usando pypdf).
2. Analiza heurísticamente metadatos clave (organismo emisor, número de expediente, fecha).
3. Invoca a MarcosAgent para generar una interpretación rigurosa y guía de actuación para el usuario.
"""

import io
import re
from typing import Dict, Any, Optional
from pypdf import PdfReader
from app.domain.agents.marcos.marcos_agent import marcos_agent
from app.utils.logger import app_logger

class DEHUService:
    @classmethod
    def extract_text_from_pdf(cls, pdf_bytes: bytes) -> str:
        """
        Extrae el texto de un archivo PDF utilizando pypdf de forma segura.
        """
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_file)
            text_parts = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            
            full_text = "\n".join(text_parts).strip()
            if not full_text:
                raise ValueError("No se pudo extraer texto del PDF (puede estar escaneado como imagen o vacío).")
            return full_text
        except Exception as e:
            app_logger.error(f"Error al extraer texto del PDF de DEHú: {e}")
            raise RuntimeError(f"Error procesando el PDF: {str(e)}")

    @classmethod
    def parse_metadata(cls, text: str) -> Dict[str, Any]:
        """
        Intenta extraer de forma heurística algunos metadatos del texto del requerimiento/notificación.
        """
        metadata = {
            "organismo": "Desconocido",
            "expediente": "No encontrado",
            "fecha_emision": "No encontrada"
        }
        
        # Buscar Organismo Emisor
        text_lower = text.lower()
        if "agencia tributaria" in text_lower or "aeat" in text_lower:
            metadata["organismo"] = "Agencia Estatal de Administración Tributaria (AEAT)"
        elif "seguridad social" in text_lower or "tgss" in text_lower or "red" in text_lower:
            metadata["organismo"] = "Tesorería General de la Seguridad Social (TGSS)"
        elif "ayuntamiento" in text_lower:
            match = re.search(r"ayuntamiento de\s+([A-Za-zÀ-ÿ\s]+)", text, re.IGNORECASE)
            if match:
                metadata["organismo"] = f"Ayuntamiento de {match.group(1).strip()}"
            else:
                metadata["organismo"] = "Administración Local (Ayuntamiento)"
        elif "jefatura" in text_lower or "tráfico" in text_lower or "dgt" in text_lower:
            metadata["organismo"] = "Dirección General de Tráfico (DGT)"
            
        # Buscar Número de Expediente o Referencia
        exp_patterns = [
            r"expediente\s*:\s*([A-Z0-9\-/]+)",
            r"ref\.?\s*:\s*([A-Z0-9\-/]+)",
            r"número\s+de\s+referencia\s*:\s*([A-Z0-9\-/]+)",
            r"nº\s+expediente\s*:\s*([A-Z0-9\-/]+)"
        ]
        for pattern in exp_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["expediente"] = match.group(1).strip()
                break
                
        # Buscar Fecha
        date_patterns = [
            r"fecha\s*:\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
            r"fecha\s+de\s+emisión\s*:\s*(\d{2}[/\-]\d{2}[/\-]\d{4})",
            r"(\d{2}\s+de\s+[a-z]+\s+de\s+\d{4})"
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["fecha_emision"] = match.group(1).strip()
                break
                
        return metadata

    @classmethod
    async def process_and_analyze_notification(cls, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Procesa el archivo PDF, extrae su texto y solicita un dictamen legal
        y guía de actuación al agente Marcos.
        """
        # 1. Extraer texto
        text = cls.extract_text_from_pdf(pdf_bytes)
        
        # 2. Extraer metadatos heurísticos
        metadata = cls.parse_metadata(text)
        
        # 3. Invocar al agente Marcos
        query = (
            "He recibido una notificación oficial a través de la DEHú. Por favor, realiza un análisis detallado "
            "de este documento. Identifica el organismo emisor, el asunto principal, las obligaciones tributarias "
            "o administrativas que se derivan, y establece los plazos exactos para responder (habitualmente 10 o 15 días hábiles). "
            "Por último, propón una guía de actuación clara con los pasos a seguir por el autónomo para resolver esta situación.\n\n"
            f"[TEXTO EXTRAÍDO DE LA NOTIFICACIÓN]:\n{text}"
        )
        
        app_logger.info(f"Delegando análisis de notificación de la DEHú (Organismo: {metadata['organismo']}) a MarcosAgent.")
        dictamen = await marcos_agent.generate_response(query)
        
        return {
            "status": "ok",
            "metadata": metadata,
            "text_preview": text[:500] + ("..." if len(text) > 500 else ""),
            "dictamen": dictamen
        }
