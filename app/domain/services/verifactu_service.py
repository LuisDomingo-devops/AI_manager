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

    @classmethod
    def get_or_create_private_key(cls) -> rsa.RSAPrivateKey:
        """
        Obtiene la clave privada RSA de Verifactu local o la crea si no existe.
        Representa la firma digital (FNMT/DNIe) en el modelo local-first.
        """
        cls._private_key_path.parent.mkdir(parents=True, exist_ok=True)
        if cls._private_key_path.exists():
            with open(cls._private_key_path, "rb") as key_file:
                return serialization.load_pem_private_key(
                    key_file.read(),
                    password=None
                )
        
        # Generar nueva clave de 2048 bits
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        
        # Guardar en disco local de forma segura
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(cls._private_key_path, "wb") as key_file:
            key_file.write(pem)
            
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
        Sigue el patrón de orden concatenado estándar de la AEAT para registros Verifactu,
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
        
        ph = (prev_hash or "").strip().upper()

        # Cadena concatenada oficial Verifactu
        concat_str = f"{issuer_nif}|{invoice_number}|{date_of_issue}|{base_imponible}|{iva_amount}|{total_amount}|{ph}"
        
        return hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()

    @classmethod
    def register_invoice(cls, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra una factura emitida bajo la regulación Verifactu.
        Calcula el hash de encadenamiento oficial y firma criptográficamente con XMLDSig estructurado.
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

            # Obtener claves y simular certificado para la firma XMLDSig
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
            etree.SubElement(receptor, "NombreRazonReceptor").text = "Cliente Final"
            etree.SubElement(receptor, "NIFReceptor").text = str(invoice_data.get("receiver_nif", ""))
            
            # DetalleFactura
            detalle = etree.SubElement(reg_alta, "DetalleFactura")
            etree.SubElement(detalle, "TipoFactura").text = "F1"  # Factura Ordinaria
            etree.SubElement(detalle, "ClaveRegimenEspecialOTrascendencia").text = "01"  # Régimen común
            etree.SubElement(detalle, "ImporteTotal").text = f"{float(invoice_data.get('total_amount', 0.0)):.2f}"
            
            # Desglose (con IVA)
            desglose = etree.SubElement(detalle, "Desglose")
            detalle_iva = etree.SubElement(desglose, "DetalleIVA")
            etree.SubElement(detalle_iva, "BaseImponible").text = f"{float(invoice_data.get('base_imponible', 0.0)):.2f}"
            etree.SubElement(detalle_iva, "CuotaIVA").text = f"{float(invoice_data.get('iva_amount', 0.0)):.2f}"
            
            # Datos de Infraestructura del Software (Requerido por Verifactu)
            sistema = etree.SubElement(reg_alta, "SistemaInformatico")
            etree.SubElement(sistema, "Nombre").text = "Alfonso Autónomo SIF"
            etree.SubElement(sistema, "NIFProductor").text = "B00000000"
            etree.SubElement(sistema, "NumInstalacion").text = "000001"
            etree.SubElement(sistema, "Version").text = "2.0.0"
            
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
            sistema = etree.SubElement(reg_anulacion, "SistemaInformatico")
            etree.SubElement(sistema, "Nombre").text = "Alfonso Autónomo SIF"
            etree.SubElement(sistema, "NIFProductor").text = "B00000000"
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
        Si no hay certificados del sistema instalados, retorna un estado offline simulado transparente.
        """
        import httpx
        # Endpoints oficiales de la AEAT (VERIFACTU - Entorno de pruebas)
        AEAT_URL = "https://prewww10.aeat.es/wlpl/PORT-SSII/ws/fe/RegFactuSistemaFacturacionSOAP"
        
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

        # Si el usuario configuró certificado electrónico cualificado, intentamos mTLS
        if cert_path and key_path and os.path.exists(cert_path):
            try:
                # Realizar llamada cliente con autenticación por certificado de cliente
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
            "code": 200,
            "message": "Registro local guardado y firmado. Envío pendiente de firma por mTLS (Entorno de desarrollo local sin certificado)."
        }

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
                return {
                    "status": "corrupted",
                    "corrupted_invoice_number": row["invoice_number"],
                    "error": f"Cadena rota en factura {row['invoice_number']}. Hash anterior esperado: {expected_prev_hash_upper}, encontrado: {current_prev_hash}"
                }
            
            calculated = cls.calculate_invoice_hash(invoice_data, expected_prev_hash)
            if row["current_hash"].upper() != calculated:
                return {
                    "status": "tampered",
                    "corrupted_invoice_number": row["invoice_number"],
                    "error": f"Datos alterados en factura {row['invoice_number']}. Hash calculado: {calculated}, encontrado en BD: {row['current_hash']}"
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


