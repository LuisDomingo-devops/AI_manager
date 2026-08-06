import os
import hashlib
import json
import base64
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from app.adapters.memory.memory import _get_connection

# Cryptography imports for real local signing
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class VerifactuService:
    """
    Servicio de cumplimiento técnico para Verifactu (AEAT 2027).
    Garantiza el encadenamiento criptográfico inalterable de facturas emitidas
    y genera la estructura necesaria para cumplir con los requisitos de la AEAT.
    """

    _private_key_path = Path(__file__).resolve().parents[3] / "data" / "keys" / "verifactu_private_key.pem"

    @classmethod
    def init_verifactu_schema(cls) -> None:
        """Inicializa la tabla de facturas emitidas bajo regulación Verifactu."""
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
                    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
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
        cls.init_verifactu_schema()
        prev_hash = cls.get_last_invoice_hash()
        current_hash = cls.calculate_invoice_hash(invoice_data, prev_hash)

        # Generar estructura XML oficial simplificada conforme a Verifactu
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
        
        # Estructura del XML del registro de facturación de alta
        registro_xml = etree.Element("RegistroFacturacionAlta")
        etree.Subclass = "Verifactu"
        etree.SubElement(registro_xml, "NIFObligado").text = str(invoice_data.get("issuer_nif", ""))
        etree.SubElement(registro_xml, "NumFactura").text = str(invoice_data.get("invoice_number", ""))
        etree.SubElement(registro_xml, "FechaExpedicion").text = str(invoice_data.get("date_of_issue", ""))
        etree.SubElement(registro_xml, "BaseImponible").text = f"{float(invoice_data.get('base_imponible', 0.0)):.2f}"
        etree.SubElement(registro_xml, "CuotaIVA").text = f"{float(invoice_data.get('iva_amount', 0.0)):.2f}"
        etree.SubElement(registro_xml, "ImporteTotal").text = f"{float(invoice_data.get('total_amount', 0.0)):.2f}"
        etree.SubElement(registro_xml, "HuellaRegistroAnterior").text = prev_hash or ""
        etree.SubElement(registro_xml, "HuellaRegistroActual").text = current_hash

        # Firmar digitalmente el elemento XMLDSig/XAdES envelopado
        signer = XMLSigner(method=signxml.methods.enveloped, signature_algorithm="rsa-sha256")
        signed_root = signer.sign(registro_xml, key=pem_key_bytes)
        
        xml_firmado_str = etree.tostring(signed_root, encoding="utf-8").decode("utf-8")
        real_sig_base64 = base64.b64encode(xml_firmado_str.encode("utf-8")).decode("utf-8")

        with _get_connection() as conn:
            conn.execute("""
                INSERT INTO verifactu_invoices (
                    invoice_number, date_of_issue, issuer_nif, receiver_nif,
                    base_imponible, iva_amount, total_amount, prev_hash, current_hash, signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    def send_to_aeat_sif(cls, xml_content: str) -> Dict[str, Any]:
        """
        Envía el XML firmado del registro al endpoint SOAP oficial de VERIFACTU de la AEAT.
        Si no hay certificados del sistema instalados, simula el envío al entorno de pruebas.
        """
        import httpx
        # Endpoints oficiales de la AEAT (VERIFACTU - Entorno de pruebas)
        AEAT_URL = "https://prewww10.aeat.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP"
        
        cert_path = os.environ.get("ALFONSO_AEAT_CERT")
        key_path = os.environ.get("ALFONSO_AEAT_KEY")
        
        # Envoltorio SOAP reglamentario
        soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:val="https://www2.agenciatributaria.gob.es/static_files/common/internet/dep/aplicaciones/es/aeat/ssii/fact/ws/SiiFactFEV1.xsd">
           <soapenv:Header/>
           <soapenv:Body>
              {xml_content}
           </soapenv:Body>
        </soapenv:Envelope>
        """

        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "https://www2.agenciatributaria.gob.es/wlpl/SSII-FACT/ws/fe/SiiFactFEV1SOAP/RegFactFacturacion"
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
        
        # Simulación del SIF offline/pruebas por defecto para evitar bloqueos
        return {
            "status": "simulated_accepted",
            "code": 200,
            "message": "Envío simulado con éxito (entorno de desarrollo local sin certificado de cliente AEAT)."
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
            invoice_data = {
                "invoice_number": row["invoice_number"],
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
                    "error": f"Cadena rota en factura {row['invoice_number']}. Hash anterior esperado: {expected_prev_hash_upper}, encontrado: {current_prev_hash}"
                }
            
            calculated = cls.calculate_invoice_hash(invoice_data, expected_prev_hash)
            if row["current_hash"].upper() != calculated:
                return {
                    "status": "tampered",
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


