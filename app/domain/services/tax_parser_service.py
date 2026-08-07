"""
TAX PARSER SERVICE — Servicio de extracción de datos para facturas y modelos fiscales.

¿QUÉ HACE?
Procesa archivos de facturas y modelos fiscales (PDF, imágenes, texto) usando OCR local o
extracción estructurada, clasifica las facturas, las persiste en SQLite y genera agregados trimestrales.
"""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from PIL import Image
try:
    import pytesseract
except ImportError:
    pytesseract = None

from app.config import settings
from app.adapters.memory.memory import _get_connection, DB_PATH
from app.utils.logger import app_logger

# Expresiones regulares para NIF español (A1234567B, 12345678Z, etc.)
NIF_REGEX = re.compile(r'\b[A-HJ-NP-SUVWXY\d]\d{7}[A-Z\d]\b', re.IGNORECASE)

# Expresiones regulares para fechas comunes
DATE_REGEX = re.compile(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b')
DATE_ISO_REGEX = re.compile(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b')

# Expresiones regulares para importes
MONEY_REGEX = re.compile(r'\b\d+(?:[.,]\d{2})?\b')


def extract_text_from_file(file_path: str) -> str:
    """
    Extrae texto de un archivo utilizando OCR si es imagen, o leyéndolo si es texto.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"El archivo no existe: {file_path}")

    ext = path.suffix.lower()
    
    # Si es imagen, intentamos OCR
    if ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".gif"]:
        if pytesseract is None:
            app_logger.warning("pytesseract no está instalado. No se puede realizar OCR local.")
            return f"[ERROR: OCR no disponible] Imagen: {path.name}"
        try:
            # Intentar configurar la ruta de tesseract en Windows si existe en ubicaciones comunes
            if os.name == "nt" and not getattr(pytesseract.pytesseract, "tesseract_cmd", None):
                common_paths = [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]
                for cp in common_paths:
                    if os.path.exists(cp):
                        pytesseract.pytesseract.tesseract_cmd = cp
                        break

            with Image.open(path) as img:
                text = pytesseract.image_to_string(img, lang="spa")
                return text
        except Exception as e:
            app_logger.error(f"Error ejecutando OCR en {file_path}: {str(e)}")
            return f"[ERROR OCR: {str(e)}] Imagen: {path.name}"
    
    # Si es archivo de texto plano o markdown
    elif ext in [".txt", ".csv", ".json", ".xml", ".md"]:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            app_logger.error(f"Error leyendo archivo de texto {file_path}: {str(e)}")
            return f"[ERROR LECTURA: {str(e)}] Archivo: {path.name}"
            
    # Si es un archivo PDF
    elif ext == ".pdf":
        text = ""
        # 1. Intentar con pdfplumber
        try:
            import pdfplumber
            app_logger.info(f"Intentando extraer texto de PDF usando pdfplumber: {file_path}")
            with pdfplumber.open(path) as pdf:
                pages_text = []
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                text = "\n".join(pages_text).strip()
        except ImportError:
            app_logger.warning("pdfplumber no está instalado, se intentará usar pypdf.")
        except Exception as e:
            app_logger.error(f"Error extrayendo texto con pdfplumber en {file_path}: {str(e)}")

        # 2. Intentar con pypdf
        if not text:
            try:
                import pypdf
                app_logger.info(f"Intentando extraer texto de PDF usando pypdf: {file_path}")
                reader = pypdf.PdfReader(path)
                pages_text = []
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        pages_text.append(page_text)
                text = "\n".join(pages_text).strip()
            except ImportError:
                app_logger.warning("pypdf no está instalado.")
            except Exception as e:
                app_logger.error(f"Error extrayendo texto con pypdf en {file_path}: {str(e)}")

        # 3. Si el texto está vacío (PDF escaneado/imagen), intentar OCR con pdf2image + pytesseract
        if not text:
            app_logger.warning(f"El PDF parece estar escaneado o vacío: {file_path}. Intentando fallback a OCR...")
            try:
                from pdf2image import convert_from_path
                if pytesseract is not None:
                    # Configurar tesseract si no está configurado
                    if os.name == "nt" and not getattr(pytesseract.pytesseract, "tesseract_cmd", None):
                        common_paths = [
                            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        ]
                        for cp in common_paths:
                            if os.path.exists(cp):
                                pytesseract.pytesseract.tesseract_cmd = cp
                                break
                    
                    app_logger.info(f"Convirtiendo PDF a imágenes para OCR: {file_path}")
                    images = convert_from_path(path)
                    ocr_pages = []
                    for img in images:
                        page_text = pytesseract.image_to_string(img, lang="spa")
                        ocr_pages.append(page_text)
                    text = "\n".join(ocr_pages).strip()
            except Exception as ocr_err:
                app_logger.error(f"No se pudo realizar OCR en el PDF: {str(ocr_err)}")

        if not text:
            return f"[ERROR: El PDF está escaneado o vacío y no se pudo aplicar OCR] Archivo: {path.name}"

        return text
        
    # Para otros formatos, devolvemos una representación básica o intentamos leer como texto
    else:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return f"[ERROR FORMATO NO SOPORTADO] Archivo: {path.name}"


class TaxParserService:
    @staticmethod
    def parse_invoice_text(text: str, user_nif: str = None) -> Dict[str, Any]:
        """
        Parsea el texto extraído de una factura para obtener campos clave.
        """
        if not user_nif:
            user_nif = settings.ALFONSO_USER_NIF

        user_nif_clean = user_nif.strip().upper()

        # 1. Buscar NIFs
        nifs = [n.upper() for n in NIF_REGEX.findall(text)]
        # Eliminar duplicados manteniendo el orden
        unique_nifs = []
        for n in nifs:
            if n not in unique_nifs:
                unique_nifs.append(n)

        issuer_nif = None
        receiver_nif = None

        if len(unique_nifs) >= 2:
            # Asumimos que el primer NIF suele ser del Emisor y el segundo del Receptor
            issuer_nif = unique_nifs[0]
            receiver_nif = unique_nifs[1]
        elif len(unique_nifs) == 1:
            # Si solo hay uno, miramos si es el del usuario
            found_nif = unique_nifs[0]
            if found_nif == user_nif_clean:
                # Si el encontrado es el del usuario, puede ser emisor o receptor.
                # Buscaremos palabras clave para determinar
                if re.search(r'(cliente|receptor|destinatario|facturar a)\b.*' + found_nif, text, re.IGNORECASE | re.DOTALL):
                    receiver_nif = found_nif
                else:
                    issuer_nif = found_nif
            else:
                # Si no es el del usuario, asumimos que es el emisor
                issuer_nif = found_nif
                receiver_nif = user_nif_clean

        # Si faltan NIFs y no coinciden, rellenamos con el NIF del usuario por defecto
        if not issuer_nif and not receiver_nif:
            issuer_nif = "ES00000000T"
            receiver_nif = user_nif_clean
        elif not issuer_nif:
            issuer_nif = "ES00000000T" if receiver_nif == user_nif_clean else user_nif_clean
        elif not receiver_nif:
            receiver_nif = "ES00000000T" if issuer_nif == user_nif_clean else user_nif_clean

        # Clasificación de categoría (ingreso/gasto)
        category = "expense" if receiver_nif == user_nif_clean else "income"

        # 2. Buscar Fecha
        date_str = None
        year = None
        quarter = None

        # Intentar buscar fecha formato ISO YYYY-MM-DD
        iso_match = DATE_ISO_REGEX.search(text)
        if iso_match:
            yyyy, mm, dd = iso_match.groups()
            date_str = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
        else:
            std_match = DATE_REGEX.search(text)
            if std_match:
                d, m, y = std_match.groups()
                if len(y) == 2:
                    y = "20" + y
                date_str = f"{y}-{m.zfill(2)}-{d.zfill(2)}"

        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                year = dt.year
                quarter = (dt.month - 1) // 3 + 1
            except ValueError:
                pass

        if not date_str:
            # Fallback a fecha de hoy si no se detecta
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            year = now.year
            quarter = (now.month - 1) // 3 + 1

        # 3. Nombres de emisor/receptor heurísticos
        # Buscamos líneas que contengan "Emisor", "Proveedor", "Cliente", "Factura de"
        issuer_name = "Proveedor Desconocido" if category == "expense" else settings.ALFONSO_USER_NAME
        receiver_name = settings.ALFONSO_USER_NAME if category == "expense" else "Cliente Desconocido"

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines[:10]:
            if "emisor" in line.lower() or "proveedor" in line.lower():
                clean_line = re.sub(r'(emisor|proveedor|nif|cif|:)', '', line, flags=re.IGNORECASE).strip()
                if clean_line and len(clean_line) > 3:
                    issuer_name = clean_line
            elif "cliente" in line.lower() or "receptor" in line.lower():
                clean_line = re.sub(r'(cliente|receptor|nif|cif|:)', '', line, flags=re.IGNORECASE).strip()
                if clean_line and len(clean_line) > 3:
                    receiver_name = clean_line

        # 4. Buscar Importes (Base, IVA, IRPF, Total)
        base_imponible = 0.0
        iva_rate = 21.0
        iva_amount = 0.0
        irpf_rate = 0.0
        irpf_amount = 0.0
        total_amount = 0.0

        # Heurística para buscar números
        # Buscamos patrones del tipo "Total: 123,45" o "Base: 100.00"
        text_lower = text.lower()

        def parse_number(val_str: str) -> float:
            # Limpiar símbolos de moneda y espacios
            val_str = val_str.replace("€", "").replace("$", "").strip()
            # Si hay puntos y comas, determinar decimales
            if "," in val_str and "." in val_str:
                # Formato europeo: 1.234,56
                val_str = val_str.replace(".", "").replace(",", ".")
            elif "," in val_str:
                # Formato 1234,56
                val_str = val_str.replace(",", ".")
            try:
                return float(val_str)
            except ValueError:
                return 0.0

        # Buscar IVA rate
        iva_rate_match = re.search(r'(?:iva|i\.v\.a\.)\s*(\d+)\s*%', text_lower)
        if iva_rate_match:
            iva_rate = float(iva_rate_match.group(1))

        # Buscar IRPF rate
        irpf_rate_match = re.search(r'(?:irpf|i\.r\.p\.f\.|retenci[oó]n)[^0-9%-]*?(-?\d+)\s*%', text_lower)
        if irpf_rate_match:
            irpf_rate = abs(float(irpf_rate_match.group(1)))

        # Buscar total de forma prioritaria
        total_matches = re.findall(r'(?:total|importe total|a pagar|total factura)\s*(?:[a-z\s]+)?[\s:]*([0-9.,\s]+(?:€|\b))', text_lower)
        if total_matches:
            # Tomamos el último número válido
            for m in reversed(total_matches):
                val = parse_number(m)
                if val > 0:
                    total_amount = val
                    break

        # Buscar base imponible
        base_matches = re.findall(r'(?:base imponible|subtotal|base|neto)[\s:]*([0-9.,\s]+(?:€|\b))', text_lower)
        if base_matches:
            for m in reversed(base_matches):
                val = parse_number(m)
                if val > 0:
                    base_imponible = val
                    break

        # Si no encontramos Base ni Total, pero vemos números en el texto
        if base_imponible == 0.0 and total_amount == 0.0:
            # Buscar todos los importes posibles y tomar el mayor como Total
            numbers = []
            for m in re.finditer(r'\b\d{1,3}(?:\.\d{3})*(?:,\d{2})\b|\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b|\b\d+(?:[.,]\d{2})\b', text):
                val = parse_number(m.group(0))
                if val > 0:
                    numbers.append(val)
            if numbers:
                total_amount = max(numbers)
                # Si tenemos total, recalculamos base imponible hacia atrás por defecto (asumiendo IVA 21%)
                base_imponible = round(total_amount / (1 + (iva_rate / 100.0)), 2)
                iva_amount = round(total_amount - base_imponible, 2)

        # Recalcular coherencia si falta alguna cantidad
        if base_imponible > 0.0 and total_amount == 0.0:
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)
            total_amount = round(base_imponible + iva_amount - irpf_amount, 2)
        elif total_amount > 0.0 and base_imponible > 0.0:
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)
        elif total_amount > 0.0 and base_imponible == 0.0:
            # Estimar
            divisor = 1.0 + (iva_rate / 100.0) - (irpf_rate / 100.0)
            base_imponible = round(total_amount / divisor, 2)
            iva_amount = round(base_imponible * (iva_rate / 100.0), 2)
            irpf_amount = round(base_imponible * (irpf_rate / 100.0), 2)

        # Reglas aritméticas de validación deterministas estrictas
        expected_total = round(base_imponible + iva_amount - irpf_amount, 2)
        if abs(total_amount - expected_total) > 0.05:
            # Forzar corrección o levantar aviso de inconsistencia
            app_logger.warning(f"Incoherencia aritmética en factura detectada. Total leído: {total_amount}, Esperado: {expected_total}. Ajustando valores.")
            total_amount = expected_total

        invoice_id_match = re.search(r'\b(?:factura\s+de\s+)([A-Za-z0-9 ]+)|(?:factura(?:\s+(?:n[uú]mero|nº|num))?|n[uú]mero|nº|num)[\s#:]*([A-Za-z0-9\-]*\d[A-Za-z0-9\-]*)', text_lower)
        invoice_id = (invoice_id_match.group(1) or invoice_id_match.group(2)).upper().strip() if invoice_id_match else f"FAC-{int(datetime.now().timestamp())}"

        # Validaciones de campos obligatorios requeridos por VERIFACTU
        if not issuer_nif or not receiver_nif:
            raise ValueError("Los NIFs del emisor y receptor son requeridos para la validez tributaria de la factura.")

        return {
            "invoice_id": invoice_id,
            "date": date_str,
            "issuer_name": issuer_name,
            "issuer_nif": issuer_nif,
            "receiver_name": receiver_name,
            "receiver_nif": receiver_nif,
            "base_imponible": base_imponible,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "irpf_rate": irpf_rate,
            "irpf_amount": irpf_amount,
            "total_amount": total_amount,
            "category": category,
            "quarter": quarter,
            "year": year
        }

    @classmethod
    def save_invoice_to_db(cls, data: Dict[str, Any], file_path: str = "") -> int:
        """
        Persiste los datos de una factura en la base de datos SQLite.
        """
        from app.domain.schemas import InvoiceSchema
        from app.utils.encryption import encryptor
        
        # Validar y normalizar datos contables mediante Pydantic
        validated_data = InvoiceSchema(**data).model_dump()
        data = validated_data
        
        # Control de duplicados: Buscar de forma eficiente usando blind_index (O(1)) sin descifrar en bucle
        target_invoice_id = str(data.get("invoice_id", "")).strip().upper()
        target_issuer_nif = str(data.get("issuer_nif", "")).strip().upper()
        
        import hashlib
        blind_raw = f"{target_invoice_id}:{target_issuer_nif}".encode("utf-8")
        blind_index = hashlib.sha256(blind_raw).hexdigest()

        if target_invoice_id and target_issuer_nif:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM invoices WHERE blind_index = ? LIMIT 1", (blind_index,))
                row = cursor.fetchone()
                if row:
                    raise ValueError(f"Factura duplicada detectada: {target_invoice_id} del emisor {target_issuer_nif}")

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO invoices (
                    invoice_id, date, issuer_name, issuer_nif, receiver_name, receiver_nif,
                    base_imponible, iva_rate, iva_amount, irpf_rate, irpf_amount, total_amount,
                    category, quarter, year, file_path, blind_index
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                encryptor.encrypt(data["invoice_id"]),
                encryptor.encrypt(data["date"]),
                encryptor.encrypt(data["issuer_name"]),
                encryptor.encrypt(data["issuer_nif"]),
                encryptor.encrypt(data["receiver_name"]),
                encryptor.encrypt(data["receiver_nif"]),
                encryptor.encrypt(str(data["base_imponible"])),
                encryptor.encrypt(str(data["iva_rate"])),
                encryptor.encrypt(str(data["iva_amount"])),
                encryptor.encrypt(str(data["irpf_rate"])),
                encryptor.encrypt(str(data["irpf_amount"])),
                encryptor.encrypt(str(data["total_amount"])),
                data["category"],
                data["quarter"],
                data["year"],
                encryptor.encrypt(file_path),
                blind_index
            ))
            conn.commit()
            last_id = cursor.lastrowid

        # Generar asiento contable PGC por partida doble de forma transparente
        try:
            from app.domain.services.ledger_service import LedgerService
            LedgerService.record_invoice_asiento(data)
        except Exception as cont_err:
            app_logger.warning("No se pudo generar el asiento contable automáticamente: %s", cont_err)

        # Sincronizar con el Excel local de forma asíncrona/segura
        try:
            from app.domain.services.excel_sync import ExcelSyncService
            ExcelSyncService.sync_invoices_to_excel()
        except Exception as xls_err:
            app_logger.warning("No se pudo sincronizar con el archivo Excel local: %s", xls_err)

        return last_id

    @classmethod
    def parse_tax_model_text(cls, text: str) -> Dict[str, Any]:
        """
        Parsea declaraciones de impuestos de la AEAT (Modelo 303 o 130).
        """
        text_lower = text.lower()
        model_name = None
        if "modelo 303" in text_lower or "303" in text_lower:
            model_name = "Modelo 303"
        elif "modelo 130" in text_lower or "130" in text_lower:
            model_name = "Modelo 130"

        # Buscar año e trimestre
        year_match = re.search(r'\b(202\d)\b', text)
        year = int(year_match.group(1)) if year_match else datetime.now().year

        quarter_match = re.search(r'\b([1-4])\s*(?:trimestre|trim|[tTqQ°º])\b', text_lower)
        quarter = int(quarter_match.group(1)) if quarter_match else 1

        resultado = 0.0
        # Buscar casillas clave
        # En el 303, la casilla 71 o 88 es el resultado final. En el 130, la casilla 19.
        # Buscaremos patrones del tipo "casilla 71: 123,45" o similares.
        boxes = {}
        for m in re.finditer(r'(?:casilla|box|\[)\s*(\d+)(?:\]|[\s:]+)(?:[a-záéíóúñ\s]+[:\s]+)?([0-9.,-]+)', text_lower):
            box_num = int(m.group(1))
            val_str = m.group(2).replace(".", "").replace(",", ".")
            try:
                boxes[box_num] = float(val_str)
            except ValueError:
                pass

        if model_name == "Modelo 303":
            # Casilla 71 es resultado ordinario de liquidación
            resultado = boxes.get(71, boxes.get(88, boxes.get(46, 0.0)))
        elif model_name == "Modelo 130":
            # Casilla 19 es el resultado a ingresar
            resultado = boxes.get(19, boxes.get(3, 0.0))

        # Si no encontramos casillas específicas, buscamos "resultado a ingresar" o "resultado liquidación"
        if resultado == 0.0:
            res_match = re.search(r'(?:resultado|a ingresar|a devolver)[\s:]*([0-9.,-]+)', text_lower)
            if res_match:
                val_str = res_match.group(1).replace(".", "").replace(",", ".")
                try:
                    resultado = float(val_str)
                except ValueError:
                    pass

        return {
            "model": model_name or "Modelo Desconocido",
            "year": year,
            "quarter": quarter,
            "resultado": resultado,
            "extracted_boxes": boxes
        }

    @classmethod
    def get_quarterly_aggregates(cls, year: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Calcula agregados trimestrales agrupados por año y trimestre.
        """
        query = """
            SELECT year, quarter, category, base_imponible, iva_amount, irpf_amount, total_amount
            FROM invoices
        """
        params = []
        if year:
            query += " WHERE year = ?"
            params.append(year)

        with _get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        from app.utils.encryption import encryptor
        
        # Agrupar por año y trimestre
        groups = {}
        for r in rows:
            key = (r["year"], r["quarter"])
            if key not in groups:
                groups[key] = {
                    "year": r["year"],
                    "quarter": r["quarter"],
                    "income": {"base": 0.0, "iva": 0.0, "irpf": 0.0, "total": 0.0, "count": 0},
                    "expense": {"base": 0.0, "iva": 0.0, "irpf": 0.0, "total": 0.0, "count": 0},
                    "net_result": 0.0
                }
            
            cat = r["category"]
            if cat in ["ingreso", "income"]:
                cat = "income"
            elif cat in ["gasto", "expense"]:
                cat = "expense"
            else:
                continue

            try:
                base = float(encryptor.decrypt(r["base_imponible"]) or 0.0)
                iva = float(encryptor.decrypt(r["iva_amount"]) or 0.0)
                irpf = float(encryptor.decrypt(r["irpf_amount"]) or 0.0)
                total = float(encryptor.decrypt(r["total_amount"]) or 0.0)
            except Exception:
                base = iva = irpf = total = 0.0

            groups[key][cat]["base"] = round(groups[key][cat]["base"] + base, 2)
            groups[key][cat]["iva"] = round(groups[key][cat]["iva"] + iva, 2)
            groups[key][cat]["irpf"] = round(groups[key][cat]["irpf"] + irpf, 2)
            groups[key][cat]["total"] = round(groups[key][cat]["total"] + total, 2)
            groups[key][cat]["count"] += 1
                
        results = []
        # Calcular resultado neto (Ingreso Total - Gasto Total)
        for g in groups.values():
            g["net_result"] = round(g["income"]["total"] - g["expense"]["total"], 2)
            results.append(g)

        return sorted(results, key=lambda x: (x["year"], x["quarter"]), reverse=True)
