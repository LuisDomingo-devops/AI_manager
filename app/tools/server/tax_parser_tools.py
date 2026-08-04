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
            return {
                "status": "ok",
                "success": False,
                "message": f"No se pudo extraer texto del archivo (OCR/Tesseract no disponible): {text}"
            }
            
        data = TaxParserService.parse_invoice_text(text)
        invoice_db_id = TaxParserService.save_invoice_to_db(data, file_path=file_path)
        
        # Mover la factura físicamente al Archivo Fiscal o Facturas Pendientes de Cobro
        try:
            import shutil
            import os
            from pathlib import Path
            from datetime import datetime
            from app.adapters.memory.memory import _get_connection
            from app.utils.encryption import encryptor

            src_path = Path(file_path)
            if src_path.exists():
                desktop_dir = Path(os.path.expanduser("~")) / "Desktop"
                if not desktop_dir.exists():
                    desktop_dir = Path(os.path.expanduser("~")) / "Escritorio"
                
                now_dt = datetime.now()
                year_str = str(now_dt.year)
                quarter_str = f"T{(now_dt.month - 1) // 3 + 1}"
                if data.get("date"):
                    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                        try:
                            inv_dt = datetime.strptime(data["date"], fmt)
                            year_str = str(inv_dt.year)
                            quarter_str = f"T{(inv_dt.month - 1) // 3 + 1}"
                            break
                        except Exception:
                            pass
                
                archive_base_dir = Path(__file__).resolve().parents[3] / "data" / "archivo fiscal"
                is_expense = data.get("category", "").lower() in ("gasto", "expense")
                if is_expense:
                    dest_dir = archive_base_dir / year_str / quarter_str / "Gastos"
                else:
                    dest_dir = archive_base_dir / "facturas pendientes"
                    
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_file = dest_dir / f"Factura_{data.get('invoice_id', 'unknown')}{src_path.suffix}"
                
                shutil.copy2(str(src_path), str(dest_file))
                
                conn = _get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE invoices SET file_path = ? WHERE id = ?", (encryptor.encrypt(str(dest_file)), invoice_db_id))
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            tool_logger.warning(f"No se pudo archivar físicamente la factura: {str(e)}")

        return {
            "status": "ok",
            "message": "Factura procesada y guardada correctamente.",
            "invoice_db_id": invoice_db_id,
            "data": data
        }
    except Exception as e:
        tool_logger.exception("Error al procesar la factura")
        return {
            "status": "ok",
            "success": False,
            "message": f"Error al procesar la factura: {str(e)}"
        }


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
