import logging
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger("boe_reader")

class BOEReaderService:
    """
    Servicio de ingesta y análisis diario del Boletín Oficial del Estado (BOE).
    Analiza el sumario XML oficial del BOE buscando regulaciones que afecten a autónomos.
    """

    @classmethod
    def get_boe_sumario_url(cls, date_str: str = None) -> str:
        """
        Genera la URL del sumario XML del BOE para una fecha específica (formato YYYYMMDD).
        Por defecto, usa la fecha actual.
        """
        if not date_str:
            date_str = datetime.now().strftime("%Y%m%d")
        return f"https://www.boe.es/diario_boe/xml.php?id=BOE-S-{date_str}"

    @classmethod
    async def fetch_and_parse_boe(cls, date_str: str = None) -> List[Dict[str, Any]]:
        """
        Descarga el sumario XML del BOE, filtra por palabras clave fiscales y autónomos,
        y devuelve una lista de alertas e inyecciones de leyes potenciales.
        """
        url = cls.get_boe_sumario_url(date_str)
        logger.info(f"Conectando a BOE para obtener sumario diario: {url}")
        
        keywords = ["iva", "irpf", "autónomo", "impuesto", "cotización", "hacienda", "aeat", "tributo", "pyme", "fiscal"]
        alerts = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.warning(f"No se pudo descargar el BOE del día (HTTP {response.status_code})")
                    return []

                root = ET.fromstring(response.content)
                
                # Recorrer todos los elementos del sumario del BOE
                for item in root.findall(".//item"):
                    title = item.find("titulo").text if item.find("titulo") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else ""
                    id_boe = item.attrib.get("id", "")

                    if not title:
                        continue

                    # Comprobar si el título contiene alguna de nuestras palabras clave
                    matched_words = [w for w in keywords if w in title.lower()]
                    
                    if matched_words:
                        alerts.append({
                            "id": id_boe,
                            "titulo": title,
                            "enlace": link,
                            "palabras_clave": matched_words,
                            "fecha": datetime.now().strftime("%d/%m/%Y"),
                            "procesado": False
                        })
                        logger.info(f"Alerta BOE detectada: [{', '.join(matched_words)}] -> {title[:80]}...")

        except Exception as e:
            logger.error(f"Error procesando el BOE diario: {e}")

        return alerts

    @classmethod
    async def analyze_fiscal_alerts(cls, alerts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Procesa las alertas y simula la sugerencia de nuevas reglas fiscales a inyectar
        en el motor de Alfonso local.
        """
        suggested_updates = []
        for alert in alerts:
            title = alert["titulo"].lower()
            
            # Simulación básica de RAG / Reglas
            if "iva" in title:
                suggested_updates.append({
                    "alerta_id": alert["id"],
                    "tipo": "IVA",
                    "descripcion": "Posible modificación en los tipos impositivos de IVA según BOE.",
                    "accion_sugerida": "Verificar base de datos de tipos impositivos de Alfonso.",
                    "url": alert["enlace"]
                })
            elif "cotización" in title or "autónomo" in title:
                suggested_updates.append({
                    "alerta_id": alert["id"],
                    "tipo": "Seguridad Social",
                    "descripcion": "Cambios detectados en cotizaciones o tramos de autónomos.",
                    "accion_sugerida": "Revisar tramos de cotización del régimen RETA.",
                    "url": alert["enlace"]
                })
        
        return suggested_updates
