import os
import hashlib
import json
import base64
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from app.adapters.memory.memory import _get_connection
from app.utils.logger import app_logger

# Cryptography imports for real local signing
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class VerifactuService:
    _lock = threading.Lock()
    """
    Servicio de cumplimiento técnico para Verifactu (AEAT 2027).
    Garantiza el encadenamiento criptográfico inalterable de facturas emitidas
    y genera la estructura necesaria para cumplir con los requisitos de la AEAT.
    """

    _private_key_path = Path(__file__).resolve().parents[3] / "data" / "keys" / "verifactu_private_key.pem"
    _worker_started = False

    @classmethod
    def init_verifactu_schema(cls) -> None:
        """Inicializa la tabla de facturas emitidas bajo regulación Verifactu."""
        import sqlite3
        with _get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS verifactu_invoices (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    invoice_number  TEXT NOT NULL UNIQUE,
                    date_of_issue   TEXT NOT NULL,
                    issuer_nif      TEXT NOT NULL,
                    receiver_nif    TEXT NOT NULL,
                    base_imponible  REAL NOT NULL,
                    iva_amount      REAL NOT NULL,
                    total_amount    REAL NOT NULL,
                    prev_hash       TEXT,
                    current_hash    TEXT NOT NULL,
                    signature       TEXT,
                    status          TEXT NOT NULL DEFAULT 'ALTA',
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            try:
                conn.execute("ALTER TABLE verifactu_invoices ADD COLUMN status TEXT DEFAULT 'ALTA'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE verifactu_invoices ADD COLUMN delivery_status TEXT DEFAULT 'PENDIENTE'")
            except sqlite3.OperationalError:
                pass
            try:
                conn.execute("ALTER TABLE verifactu_invoices ADD COLUMN delivery_error TEXT")
            except sqlite3.OperationalError:
                pass
                
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sif_event_log (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type      TEXT NOT NULL,
                    description     TEXT NOT NULL,
                    prev_event_hash TEXT,
                    current_hash    TEXT NOT NULL,
                    signature       TEXT NOT NULL,
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()

        # Iniciar worker de reintentos en segundo plano si no está corriendo
        if not cls._worker_started:
            cls._worker_started = True
            def run_worker():
                import time
                while True:
                    time.sleep(30)  # Cada 30 segundos escanea y reintenta
                    try:
                        cls.process_pending_deliveries()
                    except Exception:
                        pass
            t = threading.Thread(target=run_worker, daemon=True)
            t.start()

    @classmethod
    def get_or_create_private_key(cls, client_id: Optional[str] = None) -> rsa.RSAPrivateKey:
        """
        Obtiene la clave privada RSA de Verifactu local o la crea si no existe.
        Soporta aislamiento de claves por tenant (client_id).
        Representa la firma digital (FNMT/DNIe) en el modelo local-first.
        """
        from app.utils.encryption import encryptor
        from app.adapters.memory.memory import tenant_context
        
        cid = (client_id or tenant_context.get() or "default").strip().lower()
        if cid == "default":
            key_path = cls._private_key_path
        else:
            key_path = cls._private_key_path.parent / f"{cid}_verifactu_private_key.pem"

        key_path.parent.mkdir(parents=True, exist_ok=True)
        if key_path.exists():
            try:
                with open(key_path, "r", encoding="utf-8") as key_file:
                    content = key_file.read().strip()
                if content.startswith("gAAAA"):
                    decrypted_bytes = encryptor.decrypt(content).encode('utf-8')
                else:
                    raise ValueError("Plaintext key")
            except Exception:
                # Caso fallback o migración si es texto plano
                with open(key_path, "rb") as raw_file:
                    raw_pem = raw_file.read()
                try:
                    encrypted_pem = encryptor.encrypt(raw_pem.decode('utf-8'))
                    with open(key_path, "w", encoding="utf-8") as key_file:
                        key_file.write(encrypted_pem)
                except Exception:
                    pass
                decrypted_bytes = raw_pem

            return serialization.load_pem_private_key(
                decrypted_bytes,
                password=None
            )
        
        # Generar nueva clave de 2048 bits
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Guardar en disco local de forma segura/cifrada
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        encrypted_pem = encryptor.encrypt(pem.decode('utf-8'))
        with open(key_path, "w", encoding="utf-8") as key_file:
            key_file.write(encrypted_pem)
            
        return private_key

    @classmethod
    def get_last_invoice_hash(cls) -> Optional[str]:
        """Obtiene el hash criptográfico de la última factura registrada."""
        cls.init_verifactu_schema()
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT current_hash FROM verifactu_invoices ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["current_hash"] if row else None

    @classmethod
    def calculate_invoice_hash(cls, invoice_data: Dict[str, Any], prev_hash: Optional[str]) -> str:
        """
        Calcula el hash SHA-256 encadenando los datos de la factura con el hash anterior.
        Sigue el patrón de orden concatenado estándar de la AEAT para registros Verifactu (Orden HAC/1177/2024),
        devolviendo el hash en formato hexadecimal y en mayúsculas.
        """
        issuer_nif = str(invoice_data.get("issuer_nif", "")).strip().upper()
        invoice_number = str(invoice_data.get("invoice_number", "")).strip().upper()
        if invoice_number.endswith("_ANUL"):
            invoice_number = invoice_number[:-5]
        date_of_issue = str(invoice_data.get("date_of_issue", "")).strip()
        
        # Formatear números con dos decimales y punto decimal
        base_imponible = f"{float(invoice_data.get('base_imponible', 0.0)):.2f}"
        iva_amount = f"{float(invoice_data.get('iva_amount', 0.0)):.2f}"
        total_amount = f"{float(invoice_data.get('total_amount', 0.0)):.2f}"
        
        tipo_factura = str(invoice_data.get("tipo_factura", "F1" if not invoice_number.startswith("R-") else "R1")).strip().upper()
        gen_timestamp = str(invoice_data.get("gen_timestamp", "")).strip()
        
        ph = (prev_hash or "").strip().upper()

        if gen_timestamp:
            concat_str = f"{issuer_nif}|{invoice_number}|{date_of_issue}|{tipo_factura}|{iva_amount}|{total_amount}|{ph}|{gen_timestamp}"
        else:
            # Cadena concatenada oficial Verifactu
            concat_str = f"{issuer_nif}|{invoice_number}|{date_of_issue}|{base_imponible}|{iva_amount}|{total_amount}|{ph}"
        
        return hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()

    @classmethod
    def register_invoice(cls, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra una factura emitida bajo la regulación Verifactu.
        Calcula el hash de encadenamiento oficial y firma criptográficamente con XMLDSig estructurado.
        Soporta facturas ordinarias (F1) y rectificativas (R1-R5).
        """
        with cls._lock:
            # Normalizar NIF del emisor y receptor
            invoice_data["issuer_nif"] = str(invoice_data.get("issuer_nif", "")).strip().upper()
            invoice_data["receiver_nif"] = str(invoice_data.get("receiver_nif", "")).strip().upper()

            cls.init_verifactu_schema()
            prev_hash = cls.get_last_invoice_hash()
            current_hash = cls.calculate_invoice_hash(invoice_data, prev_hash)

            from lxml import etree
            import signxml
            from signxml import XMLSigner

            # Obtener claves y certificado para la firma XMLDSig por tenant
            private_key = cls.get_or_create_private_key()
            # Exportar clave pública simulando un certificado auto-firmado
            pem_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            # Obtener datos reales del obligado tributario del perfil fiscal de usuario si existen
            from app.utils.encryption import encryptor
            issuer_name = "Alfonso SIF User"
            with _get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT razon_social FROM user_profile LIMIT 1")
                    profile_row = cursor.fetchone()
                    if profile_row and profile_row["razon_social"]:
                        issuer_name = encryptor.decrypt(profile_row["razon_social"])
                except Exception:
                    pass

            # Estructura del XML oficial de Verifactu (Orden HAC/1177/2024)
            registro_xml = etree.Element("RegFactuSistemaFacturacion")
            
            # Cabecera
            cabecera = etree.SubElement(registro_xml, "Cabecera")
            obligado = etree.SubElement(cabecera, "ObligadoEmision")
            etree.SubElement(obligado, "NombreRazon").text = issuer_name
            etree.SubElement(obligado, "NIF").text = str(invoice_data.get("issuer_nif", ""))
            
            # Bloque de RegistroFacturacionAlta
            reg_alta = etree.SubElement(registro_xml, "RegistroFacturacionAlta")
            
            # IDFactura
            id_factura = etree.SubElement(reg_alta, "IDFactura")
            etree.SubElement(id_factura, "NumSerieFacturaEmisor").text = str(invoice_data.get("invoice_number", ""))
            etree.SubElement(id_factura, "FechaExpedicionFacturaEmisor").text = str(invoice_data.get("date_of_issue", ""))
            
            # Datos del emisor
            etree.SubElement(reg_alta, "NombreRazonEmisor").text = issuer_name
            
            # Datos del receptor
            receptor = etree.SubElement(reg_alta, "Receptor")
            etree.SubElement(receptor, "NombreRazonReceptor").text = str(invoice_data.get("receiver_name", "Cliente Final"))
            etree.SubElement(receptor, "NIFReceptor").text = str(invoice_data.get("receiver_nif", ""))
            
            # DetalleFactura
            detalle = etree.SubElement(reg_alta, "DetalleFactura")
            tipo_factura = str(invoice_data.get("tipo_factura", "R1" if str(invoice_data.get("invoice_number", "")).startswith("R-") else "F1"))
            etree.SubElement(detalle, "TipoFactura").text = tipo_factura
            
            # Soporte de Facturas Rectificativas (RD 1619/2012 y Orden HAC/1177/2024)
            if tipo_factura.startswith("R"):
                tipo_rect = str(invoice_data.get("tipo_rectificativa", "I")) # I = diferencias, S = sustitución
                etree.SubElement(detalle, "TipoRectificativa").text = tipo_rect
                
                facturas_rect = invoice_data.get("facturas_rectificadas", [])
                if not facturas_rect and invoice_data.get("rectified_invoice_number"):
                    facturas_rect = [{
                        "invoice_number": invoice_data.get("rectified_invoice_number"),
                        "date_of_issue": invoice_data.get("rectified_invoice_date", invoice_data.get("date_of_issue", ""))
                    }]
                
                if facturas_rect:
                    nodo_rectificadas = etree.SubElement(detalle, "FacturasRectificadas")
                    for fr in facturas_rect:
                        item_rect = etree.SubElement(nodo_rectificadas, "FacturaRectificada")
                        etree.SubElement(item_rect, "NumSerieFacturaEmisor").text = str(fr.get("invoice_number", ""))
                        etree.SubElement(item_rect, "FechaExpedicionFacturaEmisor").text = str(fr.get("date_of_issue", ""))

            etree.SubElement(detalle, "ClaveRegimenEspecialOTrascendencia").text = str(invoice_data.get("clave_regimen", "01"))  # 01 = Régimen común
            etree.SubElement(detalle, "ImporteTotal").text = f"{float(invoice_data.get('total_amount', 0.0)):.2f}"
            
            # Desglose (con IVA)
            desglose = etree.SubElement(detalle, "Desglose")
            detalle_iva = etree.SubElement(desglose, "DetalleIVA")
            detalle_iva_base = float(invoice_data.get('base_imponible', 0.0))
            detalle_iva_cuota = float(invoice_data.get('iva_amount', 0.0))
            etree.SubElement(detalle_iva, "BaseImponible").text = f"{detalle_iva_base:.2f}"
            etree.SubElement(detalle_iva, "CuotaIVA").text = f"{detalle_iva_cuota:.2f}"
            
            # Datos de Infraestructura del Software (Requerido por Verifactu)
            from app.config import settings
            sistema = etree.SubElement(reg_alta, "SistemaInformatico")
            etree.SubElement(sistema, "Nombre").text = settings.SIF_SOFTWARE_NAME
            etree.SubElement(sistema, "NIFProductor").text = settings.ALFONSO_SIF_PRODUCER_NIF
            etree.SubElement(sistema, "NumInstalacion").text = "000001"
            etree.SubElement(sistema, "Version").text = settings.SIF_VERSION
            
            # Encadenamiento criptográfico Verifactu oficial
            if prev_hash:
                encadenamiento = etree.SubElement(reg_alta, "Encadenamiento")
                registro_ant = etree.SubElement(encadenamiento, "RegistroAnterior")
                etree.SubElement(registro_ant, "Huella").text = prev_hash

            # Validar XML generado contra el esquema XSD oficial local de Veri*Factu
            xsd_path = Path(__file__).resolve().parent.parent / "schemas" / "verifactu.xsd"
            if xsd_path.exists():
                try:
                    xmlschema_doc = etree.parse(str(xsd_path))
                    xmlschema = etree.XMLSchema(xmlschema_doc)
                    xmlschema.assertValid(registro_xml)
                except Exception as xml_err:
                    app_logger.error(f"Error de validación contra el esquema XSD de Veri*Factu (Alta): {xml_err}")
                    raise ValueError(f"El XML de Veri*Factu generado no cumple el esquema XSD oficial: {xml_err}")

            # Firmar digitalmente el elemento XMLDSig/XAdES envelopado
            signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha256")
            signed_root = signer.sign(registro_xml, key=pem_key_bytes)
            
            xml_firmado_str = etree.tostring(signed_root, encoding="utf-8").decode("utf-8")
            real_sig_base64 = base64.b64encode(xml_firmado_str.encode("utf-8")).decode("utf-8")

            with _get_connection() as conn:
                conn.execute("""
                    INSERT INTO verifactu_invoices (
                        invoice_number, date_of_issue, issuer_nif, receiver_nif,
                        base_imponible, iva_amount, total_amount, prev_hash, current_hash, signature, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ALTA')
                """, (
                    invoice_data["invoice_number"],
                    invoice_data["date_of_issue"],
                    invoice_data["issuer_nif"],
                    invoice_data["receiver_nif"],
                    invoice_data["base_imponible"],
                    invoice_data["iva_amount"],
                    invoice_data["total_amount"],
                    prev_hash,
                    current_hash,
                    real_sig_base64
                ))
                conn.commit()

            # Guardar en local el XML firmado para auditar
            xml_dir = Path(__file__).resolve().parents[3] / "data" / "xml_invoices"
            xml_dir.mkdir(parents=True, exist_ok=True)
            xml_file = xml_dir / f"{invoice_data['invoice_number']}_verifactu.xml"
            with open(xml_file, "w", encoding="utf-8") as f:
                f.write(xml_firmado_str)

            # Envío inmediato (real/simulado) al Sistema Informático de Facturación (SIF) de la AEAT
            aeat_response = cls.send_to_aeat_sif(xml_firmado_str)

            # Determinar estado de envío contable
            status_map = {
                "accepted": "ENVIADO",
                "offline_simulated": "PENDIENTE"
            }
            delivery_status = status_map.get(aeat_response.get("status"), "ERROR")
            delivery_error = aeat_response.get("error") or aeat_response.get("message") if delivery_status == "ERROR" else None

            with _get_connection() as conn:
                conn.execute(
                    "UPDATE verifactu_invoices SET delivery_status = ?, delivery_error = ? WHERE invoice_number = ?",
                    (delivery_status, delivery_error, invoice_data["invoice_number"])
                )
                conn.commit()

            return {
                "status": "success",
                "invoice_number": invoice_data["invoice_number"],
                "prev_hash": prev_hash,
                "current_hash": current_hash,
                "signature": real_sig_base64,
                "aeat_delivery": aeat_response
            }

    @classmethod
    def cancel_invoice(cls, invoice_number: str) -> Dict[str, Any]:
        """
        Anula una factura registrada en Verifactu.
        Genera el XML oficial de anulación y calcula su hash encadenado.
        """
        with cls._lock:
            cls.init_verifactu_schema()
            
            # Obtener datos de la factura original
            with _get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM verifactu_invoices WHERE invoice_number = ? AND status = 'ALTA' LIMIT 1",
                    (invoice_number,)
                ).fetchone()
                
            if not row:
                return {"status": "error", "message": f"Factura {invoice_number} no encontrada o ya anulada."}

            prev_hash = cls.get_last_invoice_hash()
            
            # Preparar datos para hash de anulación
            invoice_data = {
                "invoice_number": invoice_number,
                "date_of_issue": row["date_of_issue"],
                "issuer_nif": row["issuer_nif"],
                "receiver_nif": row["receiver_nif"],
                "base_imponible": row["base_imponible"],
                "iva_amount": row["iva_amount"],
                "total_amount": row["total_amount"]
            }
            
            current_hash = cls.calculate_invoice_hash(invoice_data, prev_hash)

            from lxml import etree
            import signxml
            from signxml import XMLSigner

            # Obtener claves y firmar
            private_key = cls.get_or_create_private_key()
            pem_key_bytes = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )

            # Obtener datos reales del obligado tributario del perfil fiscal de usuario si existen
            from app.utils.encryption import encryptor
            issuer_name = "Alfonso SIF User"
            with _get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("SELECT razon_social FROM user_profile LIMIT 1")
                    profile_row = cursor.fetchone()
                    if profile_row and profile_row["razon_social"]:
                        issuer_name = encryptor.decrypt(profile_row["razon_social"])
                except Exception:
                    pass

            # Estructura XML de anulación
            registro_xml = etree.Element("RegFactuSistemaFacturacion")
            
            cabecera = etree.SubElement(registro_xml, "Cabecera")
            obligado = etree.SubElement(cabecera, "ObligadoEmision")
            etree.SubElement(obligado, "NombreRazon").text = issuer_name
            etree.SubElement(obligado, "NIF").text = row["issuer_nif"]
            
            reg_anulacion = etree.SubElement(registro_xml, "RegistroFacturacionAnulacion")
            
            # IDFacturaAnulada
            id_factura = etree.SubElement(reg_anulacion, "IDFacturaAnulada")
            etree.SubElement(id_factura, "NumSerieFacturaEmisor").text = invoice_number
            etree.SubElement(id_factura, "FechaExpedicionFacturaEmisor").text = row["date_of_issue"]
            
            # Datos del emisor
            etree.SubElement(reg_anulacion, "NombreRazonEmisor").text = issuer_name
            
            # SistemaInformatico
            from app.config import settings
            sistema = etree.SubElement(reg_anulacion, "SistemaInformatico")
            etree.SubElement(sistema, "Nombre").text = "Alfonso Autónomo SIF"
            etree.SubElement(sistema, "NIFProductor").text = settings.ALFONSO_SIF_PRODUCER_NIF
            etree.SubElement(sistema, "NumInstalacion").text = "000001"
            etree.SubElement(sistema, "Version").text = "2.0.0"
            
            # Encadenamiento
            if prev_hash:
                encadenamiento = etree.SubElement(reg_anulacion, "Encadenamiento")
                registro_ant = etree.SubElement(encadenamiento, "RegistroAnterior")
                etree.SubElement(registro_ant, "Huella").text = prev_hash

            # Validar XML generado contra el esquema XSD oficial local de Veri*Factu
            xsd_path = Path(__file__).resolve().parent.parent / "schemas" / "verifactu.xsd"
            if xsd_path.exists():
                try:
                    xmlschema_doc = etree.parse(str(xsd_path))
                    xmlschema = etree.XMLSchema(xmlschema_doc)
                    xmlschema.assertValid(registro_xml)
                except Exception as xml_err:
                    app_logger.error(f"Error de validación contra el esquema XSD de Veri*Factu (Anulación): {xml_err}")
                    raise ValueError(f"El XML de Veri*Factu generado no cumple el esquema XSD oficial: {xml_err}")

            # Firmar
            signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha256")
            signed_root = signer.sign(registro_xml, key=pem_key_bytes)
            
            xml_firmado_str = etree.tostring(signed_root, encoding="utf-8").decode("utf-8")
            real_sig_base64 = base64.b64encode(xml_firmado_str.encode("utf-8")).decode("utf-8")

            # Registrar la anulación como nueva fila con sufijo local para evitar UNIQUE constraint de SQLite
            invoice_number_local = f"{invoice_number}_ANUL"
            with _get_connection() as conn:
                # 1. Actualizar estado de la factura original a ANULADA
                conn.execute(
                    "UPDATE verifactu_invoices SET status = 'ANULADA' WHERE id = ?",
                    (row["id"],)
                )
                # 2. Insertar el registro de anulación en la cadena
                conn.execute("""
                    INSERT INTO verifactu_invoices (
                        invoice_number, date_of_issue, issuer_nif, receiver_nif,
                        base_imponible, iva_amount, total_amount, prev_hash, current_hash, signature, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ANULADA')
                """, (
                    invoice_number_local,
                    row["date_of_issue"],
                    row["issuer_nif"],
                    row["receiver_nif"],
                    row["base_imponible"],
                    row["iva_amount"],
                    row["total_amount"],
                    prev_hash,
                    current_hash,
                    real_sig_base64
                ))
                conn.commit()

            # Guardar XML local
            xml_dir = Path(__file__).resolve().parents[3] / "data" / "xml_invoices"
            xml_dir.mkdir(parents=True, exist_ok=True)
            xml_file = xml_dir / f"{invoice_number}_anulacion_verifactu.xml"
            with open(xml_file, "w", encoding="utf-8") as f:
                f.write(xml_firmado_str)

            aeat_response = cls.send_to_aeat_sif(xml_firmado_str)

            # Determinar estado de envío contable
            status_map = {
                "accepted": "ENVIADO",
                "offline_simulated": "PENDIENTE"
            }
            delivery_status = status_map.get(aeat_response.get("status"), "ERROR")
            delivery_error = aeat_response.get("error") or aeat_response.get("message") if delivery_status == "ERROR" else None

            with _get_connection() as conn:
                conn.execute(
                    "UPDATE verifactu_invoices SET delivery_status = ?, delivery_error = ? WHERE invoice_number = ?",
                    (delivery_status, delivery_error, invoice_number_local)
                )
                conn.commit()

            return {
                "status": "success",
                "invoice_number": invoice_number,
                "prev_hash": prev_hash,
                "current_hash": current_hash,
                "signature": real_sig_base64,
                "aeat_delivery": aeat_response
            }

    @classmethod
    def send_to_aeat_sif(cls, xml_content: str) -> Dict[str, Any]:
        """
        Envía el XML firmado del registro al endpoint SOAP oficial de VERIFACTU de la AEAT.
        Si no hay certificados en el perfil fiscal de usuario, retorna un estado offline simulado.
        """
        import httpx
        import tempfile
        from cryptography.hazmat.primitives.serialization import pkcs12
        from app.utils.encryption import encryptor

        # Endpoints oficiales de la AEAT (VERIFACTU - Entorno de pruebas)
        AEAT_URL = "https://prewww10.aeat.es/wlpl/PORT-SSII/ws/fe/RegFactuSistemaFacturacionSOAP"
        
        cert_path = None
        key_path = None
        cert_pem_file = None
        key_pem_file = None

        # Obtener certificado de la DB (user_profile)
        cert_path_db = None
        cert_password_db = None
        try:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cert_path, cert_password FROM user_profile LIMIT 1")
                row = cursor.fetchone()
                if row:
                    if row["cert_path"]:
                        cert_path_db = encryptor.decrypt(row["cert_path"])
                    if row["cert_password"]:
                        cert_password_db = encryptor.decrypt(row["cert_password"])
        except Exception:
            pass

        # Si hay certificado en la DB, extraer clave y cert a archivos temporales PEM
        if cert_path_db and os.path.exists(cert_path_db):
            try:
                with open(cert_path_db, "rb") as f:
                    p12_data = f.read()
                
                password = cert_password_db.encode("utf-8") if cert_password_db else None
                private_key, certificate, additional_certificates = pkcs12.load_key_and_certificates(
                    p12_data, password
                )
                
                if private_key and certificate:
                    cert_pem_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                    cert_pem_file.write(certificate.public_bytes(serialization.Encoding.PEM))
                    cert_pem_file.close()
                    
                    key_pem_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
                    key_pem_file.write(private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption()
                    ))
                    key_pem_file.close()
                    
                    cert_path = cert_pem_file.name
                    key_path = key_pem_file.name
            except Exception as cert_err:
                app_logger.warning("No se pudo cargar el certificado P12/PFX del perfil para mTLS: %s", cert_err)

        # Fallback a variables de entorno para compatibilidad y testing
        if not cert_path and not key_path:
            cert_path = os.environ.get("ALFONSO_AEAT_CERT")
            key_path = os.environ.get("ALFONSO_AEAT_KEY")

        # Envoltorio SOAP reglamentario Verifactu
        soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:val="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/RegFactuSistemaFacturacion.xsd">
           <soapenv:Header/>
           <soapenv:Body>
              {xml_content}
           </soapenv:Body>
        </soapenv:Envelope>
        """

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "https://www2.agenciatributaria.gob.es/wlpl/PORT-SSII/ws/fe/RegFactuSistemaFacturacionSOAP"
        }

        try:
            # Si se configuró certificado electrónico cualificado, realizamos mTLS real
            if cert_path and key_path and os.path.exists(cert_path):
                try:
                    with httpx.Client(cert=(cert_path, key_path), verify=True) as client:
                        response = client.post(AEAT_URL, content=soap_envelope, headers=headers, timeout=10.0)
                        if response.status_code == 200:
                            return {"status": "accepted", "code": 200, "message": "Registro aceptado por la AEAT."}
                        else:
                            return {"status": "rejected", "code": response.status_code, "error": response.text}
                except Exception as e:
                    return {"status": "incident", "message": f"Incidencia de red o TLS en el envío a la AEAT: {str(e)}"}
            
            # Simulación de pruebas offline para evitar falsas aceptaciones
            return {
                "status": "offline_simulated",
                "code": 202,
                "message": "ATENCIÓN: Registro firmado y guardado localmente, pero PENDIENTE de envío a la AEAT por falta de certificado cualificado en el perfil."
            }
        finally:
            # Limpiar archivos temporales de certificados de forma segura
            if cert_pem_file and os.path.exists(cert_pem_file.name):
                try:
                    os.remove(cert_pem_file.name)
                except OSError:
                    pass
            if key_pem_file and os.path.exists(key_pem_file.name):
                try:
                    os.remove(key_pem_file.name)
                except OSError:
                    pass

    @classmethod
    def process_pending_deliveries(cls) -> None:
        """
        Escanea y reintenta el envío de facturas que estén en estado PENDIENTE o ERROR.
        """
        with cls._lock:
            cls.init_verifactu_schema()
            with _get_connection() as conn:
                rows = conn.execute(
                    "SELECT invoice_number, status FROM verifactu_invoices WHERE delivery_status IN ('PENDIENTE', 'ERROR')"
                ).fetchall()
            
            for row in rows:
                invoice_num = row["invoice_number"]
                is_anulacion = row["status"] == "ANULADA"
                
                # Cargar el XML firmado guardado localmente
                xml_dir = Path(__file__).resolve().parents[3] / "data" / "xml_invoices"
                xml_name = f"{invoice_num.replace('_ANUL', '')}_anulacion_verifactu.xml" if is_anulacion else f"{invoice_num}_verifactu.xml"
                xml_path = xml_dir / xml_name
                
                if xml_path.exists():
                    try:
                        with open(xml_path, "r", encoding="utf-8") as f:
                            xml_content = f.read()
                        
                        aeat_response = cls.send_to_aeat_sif(xml_content)
                        
                        status_map = {
                            "accepted": "ENVIADO",
                            "offline_simulated": "PENDIENTE"
                        }
                        delivery_status = status_map.get(aeat_response.get("status"), "ERROR")
                        delivery_error = aeat_response.get("error") or aeat_response.get("message") if delivery_status == "ERROR" else None
                        
                        with _get_connection() as conn:
                            conn.execute(
                                "UPDATE verifactu_invoices SET delivery_status = ?, delivery_error = ? WHERE invoice_number = ?",
                                (delivery_status, delivery_error, invoice_num)
                            )
                            conn.commit()
                    except Exception as err:
                        app_logger.warning(f"No se pudo procesar el reenvío de la factura {invoice_num}: {err}")

    @classmethod
    def verify_chain_integrity(cls) -> Dict[str, Any]:
        """
        Verifica la integridad de toda la cadena de facturas registradas.
        Detecta cualquier modificación o manipulación de datos históricos.
        """
        cls.init_verifactu_schema()
        with _get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM verifactu_invoices ORDER BY id ASC"
            ).fetchall()

        expected_prev_hash = None
        for i, row in enumerate(rows):
            inv_num = row["invoice_number"]
            if inv_num.endswith("_ANUL"):
                inv_num = inv_num[:-5]
                
            invoice_data = {
                "invoice_number": inv_num,
                "date_of_issue": row["date_of_issue"],
                "issuer_nif": row["issuer_nif"],
                "receiver_nif": row["receiver_nif"],
                "base_imponible": row["base_imponible"],
                "iva_amount": row["iva_amount"],
                "total_amount": row["total_amount"]
            }
            # Verificar encadenamiento (comparando en mayúsculas)
            current_prev_hash = (row["prev_hash"] or "").upper() if row["prev_hash"] else None
            expected_prev_hash_upper = expected_prev_hash.upper() if expected_prev_hash else None
            
            if current_prev_hash != expected_prev_hash_upper:
                err_msg = f"Cadena rota en factura {row['invoice_number']}. Hash anterior esperado: {expected_prev_hash_upper}, encontrado: {current_prev_hash}"
                try:
                    cls.log_sif_event(
                        event_type="INTEGRITY_TAMPERING_DETECTED",
                        description=f"Alerta de integridad SIF: {err_msg}"
                    )
                except Exception:
                    pass
                return {
                    "status": "corrupted",
                    "corrupted_invoice_number": row["invoice_number"],
                    "error": err_msg
                }
            
            calculated = cls.calculate_invoice_hash(invoice_data, expected_prev_hash)
            if row["current_hash"].upper() != calculated:
                err_msg = f"Datos alterados en factura {row['invoice_number']}. Hash calculado: {calculated}, encontrado en BD: {row['current_hash']}"
                try:
                    cls.log_sif_event(
                        event_type="INTEGRITY_TAMPERING_DETECTED",
                        description=f"Alerta de integridad SIF: {err_msg}"
                    )
                except Exception:
                    pass
                return {
                    "status": "tampered",
                    "corrupted_invoice_number": row["invoice_number"],
                    "error": err_msg
                }
            expected_prev_hash = row["current_hash"]

        return {
            "status": "valid",
            "message": f"Integridad validada con éxito. Se verificaron {len(rows)} facturas sin alteraciones."
        }

    @classmethod
    def get_last_event_log_hash(cls) -> Optional[str]:
        """Obtiene el hash del último evento registrado en el log SIF."""
        cls.init_verifactu_schema()
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT current_hash FROM sif_event_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
            return row["current_hash"] if row else None

    @classmethod
    def log_sif_event(cls, event_type: str, description: str) -> str:
        """
        Registra un evento del sistema de facturación en el log de auditoría (SIF),
        calculando el hash del evento actual y encadenándolo con el anterior, firmado con la clave privada.
        """
        cls.init_verifactu_schema()
        prev_hash = cls.get_last_event_log_hash()
        
        # Generar contenido único para el hash
        timestamp = datetime.now().isoformat()
        ph = prev_hash or ""
        concat_str = f"{event_type}|{description}|{timestamp}|{ph}"
        current_hash = hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()
        
        # Firmar digitalmente con la clave privada local
        private_key = cls.get_or_create_private_key()
        signature_bytes = private_key.sign(
            current_hash.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature_bytes).decode("utf-8")
        
        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO sif_event_log (
                    event_type, description, prev_event_hash, current_hash, signature, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (event_type, description, prev_hash, current_hash, signature_b64, timestamp))
            conn.commit()
            
        return current_hash

    @classmethod
    def export_to_facturae_xml(cls, invoice_data: Dict[str, Any]) -> str:
        """
        Exporta una factura emitida al formato oficial XML Facturae v3.2.2 (B2G/FACe).
        Firma el XML con la clave/certificado disponible.
        """
        from lxml import etree
        import signxml
        from signxml import XMLSigner

        facturae = etree.Element("Facturae", xmlns="http://www.facturae.es/Facturae/v3.2.2/Facturae")
        
        # Estructura obligatoria simplificada de cabecera de Facturae
        header = etree.SubElement(facturae, "FileHeader")
        etree.SubElement(header, "SchemaVersion").text = "3.2.2"
        etree.SubElement(header, "Modality").text = "I"
        etree.SubElement(header, "Batch").text = "1"
        
        # Datos de facturación
        invoices = etree.SubElement(facturae, "Invoices")
        inv = etree.SubElement(invoices, "Invoice")
        
        header_inv = etree.SubElement(inv, "InvoiceHeader")
        etree.SubElement(header_inv, "InvoiceNumber").text = str(invoice_data.get("invoice_number", ""))
        etree.SubElement(header_inv, "InvoiceDocumentType").text = "FC"
        
        dates = etree.SubElement(inv, "InvoiceIssueData")
        etree.SubElement(dates, "IssueDate").text = str(invoice_data.get("date_of_issue", ""))
        
        totals = etree.SubElement(inv, "InvoiceTotals")
        etree.SubElement(totals, "TotalGrossAmount").text = f"{float(invoice_data.get('base_imponible', 0.0)):.2f}"
        etree.SubElement(totals, "TotalTaxOutputs").text = f"{float(invoice_data.get('iva_amount', 0.0)):.2f}"
        etree.SubElement(totals, "InvoiceTotalAmount").text = f"{float(invoice_data.get('total_amount', 0.0)):.2f}"

        # Firmar digitalmente con el certificado
        private_key = cls.get_or_create_private_key()
        pem_key_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha256")
        signed_facturae = signer.sign(facturae, key=pem_key_bytes)
        
        xml_str = etree.tostring(signed_facturae, encoding="utf-8", xml_declaration=True).decode("utf-8")
        
        # Guardar en data/facturae_xml/
        xml_dir = Path(__file__).resolve().parents[3] / "data" / "facturae_xml"
        xml_dir.mkdir(parents=True, exist_ok=True)
        xml_file = xml_dir / f"{invoice_data['invoice_number']}_facturae.xml"
        with open(xml_file, "w", encoding="utf-8") as f:
            f.write(xml_str)
            
        return xml_str

    @classmethod
    def get_compliance_declaration_dossier(cls, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Genera el Expediente Técnico y Declaración Responsable de Conformidad del SIF
        conforme al artículo 13 de la Orden HAC/1177/2024 y RD 1007/2023.
        """
        from app.config import settings
        import hashlib

        # Generar huella digital del software basada en archivos clave
        hasher = hashlib.sha256()
        try:
            core_file = Path(__file__).resolve()
            hasher.update(core_file.read_bytes())
        except Exception:
            hasher.update(settings.SIF_VERSION.encode("utf-8"))
        software_fingerprint = hasher.hexdigest()

        now_str = datetime.now().isoformat()

        statement_text = (
            f"{settings.SIF_DEVELOPER} declara bajo su expresa y exclusiva responsabilidad que el Sistema "
            f"Informático de Facturación (SIF) '{settings.SIF_SOFTWARE_NAME}', versión {settings.SIF_VERSION}, "
            f"cumple íntegramente con todos los requisitos establecidos en el artículo 29.2.j) de la Ley 58/2003 "
            f"(LGT), el Real Decreto 1007/2023 (Reglamento Veri*factu), las especificaciones técnicas de la "
            f"Orden HAC/1177/2024, el Reglamento de Facturación (RD 1619/2012) y la Ley 18/2022 (Crea y Crece). "
            "Garantiza la integridad, inalterabilidad, trazabilidad, accesibilidad y legibilidad de los registros."
        )

        # Firma digital con la clave RSA del sistema
        private_key = cls.get_or_create_private_key(client_id)
        sig_bytes = private_key.sign(
            statement_text.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        digital_signature = sig_bytes.hex()

        return {
            "status": "ok",
            "developer": settings.SIF_DEVELOPER,
            "software_name": settings.SIF_SOFTWARE_NAME,
            "version": settings.SIF_VERSION,
            "software_fingerprint_sha256": software_fingerprint,
            "certified_date": settings.SIF_CERTIFIED_DATE,
            "declaration_timestamp": now_str,
            "normativa_aplicable": [
                "Ley 58/2003, de 17 de diciembre, General Tributaria (Art. 29.2.j y 201 bis)",
                "Real Decreto 1007/2023, de 5 de diciembre (Reglamento SIF / Veri*factu)",
                "Orden HAC/1177/2024, de 17 de octubre (Especificaciones técnicas, huella y QR)",
                "Real Decreto 1619/2012, de 30 de noviembre (Reglamento de Facturación)",
                "Ley 18/2022, de 28 de septiembre (Crea y Crece - Factura Electrónica B2B)"
            ],
            "expediente_evidencias_tecnicas": {
                "encadenamiento_criptografico_sha256": "CONFORME (Anexo I y II Orden HAC/1177/2024)",
                "registro_eventos_sif_log": "CONFORME (Art. 12 Orden HAC/1177/2024)",
                "codigo_qr_cotejo_aeat": "CONFORME (Anexo III Orden HAC/1177/2024)",
                "facturacion_rectificativa": "CONFORME (Series R-YYYY-XXX y tipos R1-R5)",
                "aislamiento_multitenant_rsa": "CONFORME (Claves privadas y certificados por tenant)",
                "partida_doble_estricta": "CONFORME (Debe == Haber y soporte IRPF)",
                "factura_electronica_ubl_en16931": "CONFORME (Peppol BIS 3.0 y Facturae 3.2.2)",
                "estados_comerciales_b2b": "CONFORME (5 estados obligatorios Ley 18/2022)"
            },
            "statement": statement_text,
            "digital_signature": digital_signature
        }



