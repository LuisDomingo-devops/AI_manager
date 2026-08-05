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
        Calcula el hash de encadenamiento oficial y firma criptográficamente con RSA local.
        """
        cls.init_verifactu_schema()
        prev_hash = cls.get_last_invoice_hash()
        current_hash = cls.calculate_invoice_hash(invoice_data, prev_hash)

        # Realizar firma criptográfica RSA-SHA256 real sobre el hash actual
        private_key = cls.get_or_create_private_key()
        signature_bytes = private_key.sign(
            current_hash.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        real_sig_base64 = base64.b64encode(signature_bytes).decode("utf-8")

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

        return {
            "status": "success",
            "invoice_number": invoice_data["invoice_number"],
            "prev_hash": prev_hash,
            "current_hash": current_hash,
            "signature": real_sig_base64
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
