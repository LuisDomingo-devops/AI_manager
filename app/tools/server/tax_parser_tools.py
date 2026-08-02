"""
TAX PARSER TOOLS — Herramientas para procesar facturas e impuestos de Alfonso.

¿QUÉ HACE?
Expone las funciones del servicio TaxParserService para que el LLM las invoque.
"""

from typing import Optional
from app.domain.services.tax_parser_service import TaxParserService, extract_text_from_file
from app.utils.logger import tool_logger


async def parse_invoice(file_path: str) -> dict:
    """
    Lee y extrae la información estructurada de una factura (desde una imagen o texto plano)
    y la guarda en la base de datos local SQLite.
    
    Parámetros:
    - file_path: Ruta absoluta o relativa al archivo de la factura.
    """
    try:
        tool_logger.info(f"Iniciando el procesamiento de factura: {file_path}")
        text = extract_text_from_file(file_path)
        
        # Si hubo un error en la extracción, el texto comenzará con "[ERROR"
        if text.startswith("[ERROR"):
            return {"status": "error", "message": f"No se pudo extraer texto del archivo: {text}"}
            
        data = TaxParserService.parse_invoice_text(text)
        invoice_db_id = TaxParserService.save_invoice_to_db(data, file_path=file_path)
        
        return {
            "status": "ok",
            "message": "Factura procesada y guardada correctamente.",
            "invoice_db_id": invoice_db_id,
            "data": data
        }
    except Exception as e:
        tool_logger.exception("Error al procesar la factura")
        return {"status": "error", "message": f"Error al procesar la factura: {str(e)}"}


async def parse_tax_model(file_path: str) -> dict:
    """
    Lee y extrae la información de una declaración fiscal de la AEAT (Modelo 303 o 130).
    
    Parámetros:
    - file_path: Ruta absoluta o relativa al archivo del modelo fiscal.
    """
    try:
        tool_logger.info(f"Iniciando el procesamiento del modelo fiscal: {file_path}")
        text = extract_text_from_file(file_path)
        
        if text.startswith("[ERROR"):
            return {"status": "error", "message": f"No se pudo extraer texto del archivo: {text}"}
            
        data = TaxParserService.parse_tax_model_text(text)
        return {
            "status": "ok",
            "message": "Modelo fiscal procesado correctamente.",
            "data": data
        }
    except Exception as e:
        tool_logger.exception("Error al procesar el modelo fiscal")
        return {"status": "error", "message": f"Error al procesar el modelo fiscal: {str(e)}"}


async def get_quarterly_aggregates(year: Optional[int] = None) -> dict:
    """
    Obtiene los agregados trimestrales de ingresos y gastos calculados a partir de las facturas guardadas.
    
    Parámetros:
    - year: Año opcional (ej. 2026) para filtrar los agregados.
    """
    try:
        tool_logger.info(f"Calculando agregados trimestrales para el año: {year or 'todos'}")
        aggregates = TaxParserService.get_quarterly_aggregates(year=year)
        return {
            "status": "ok",
            "year_filter": year,
            "aggregates": aggregates
        }
    except Exception as e:
        tool_logger.exception("Error al calcular agregados trimestrales")
        return {"status": "error", "message": f"Error al obtener agregados: {str(e)}"}


# Registro de herramientas exportado para la carga dinámica de plugins
TOOLS = {
    "parse_invoice": parse_invoice,
    "parse_tax_model": parse_tax_model,
    "get_quarterly_aggregates": get_quarterly_aggregates,
}
