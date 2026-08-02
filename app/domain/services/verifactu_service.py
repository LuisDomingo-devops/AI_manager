import os
import hashlib
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from app.adapters.memory.memory import _get_connection

class VerifactuService:
    """
    Servicio de cumplimiento técnico para Verifactu (AEAT 2027).
    Garantiza el encadenamiento criptográfico inalterable de facturas emitidas
    y genera la estructura necesaria para cumplir con los requisitos de la AEAT.
    """

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
        Garantiza la inalterabilidad histórica (similar a una cadena de bloques).
        """
        # Normalizar datos para asegurar consistencia de hash
        serialized_data = {
            "invoice_number": str(invoice_data.get("invoice_number", "")).strip(),
            "date_of_issue": str(invoice_data.get("date_of_issue", "")).strip(),
            "issuer_nif": str(invoice_data.get("issuer_nif", "")).strip(),
            "receiver_nif": str(invoice_data.get("receiver_nif", "")).strip(),
            "base_imponible": round(float(invoice_data.get("base_imponible", 0.0)), 2),
            "iva_amount": round(float(invoice_data.get("iva_amount", 0.0)), 2),
            "total_amount": round(float(invoice_data.get("total_amount", 0.0)), 2),
            "prev_hash": prev_hash or ""
        }
        data_string = json.dumps(serialized_data, sort_keys=True)
        return hashlib.sha256(data_string.encode("utf-8")).hexdigest()

    @classmethod
    def register_invoice(cls, invoice_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Registra una factura emitida bajo la regulación Verifactu.
        Calcula el hash de encadenamiento y simula la firma digital XAdES requerida.
        """
        cls.init_verifactu_schema()
        prev_hash = cls.get_last_invoice_hash()
        current_hash = cls.calculate_invoice_hash(invoice_data, prev_hash)

        # Simular firma digital con certificado FNMT/DNIe
        # En producción real se utiliza xmlsig/cryptography con clave privada
        signature_payload = f"SIGNATURE_OF({current_hash})"
        simulated_sig = hashlib.sha256(signature_payload.encode("utf-8")).hexdigest()

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
                simulated_sig
            ))
            conn.commit()

        return {
            "status": "success",
            "invoice_number": invoice_data["invoice_number"],
            "prev_hash": prev_hash,
            "current_hash": current_hash,
            "signature": simulated_sig
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
            # Verificar encadenamiento
            if row["prev_hash"] != expected_prev_hash:
                return {
                    "status": "corrupted",
                    "error": f"Cadena rota en factura {row['invoice_number']}. Hash anterior esperado: {expected_prev_hash}, encontrado: {row['prev_hash']}"
                }
            
            calculated = cls.calculate_invoice_hash(invoice_data, expected_prev_hash)
            if row["current_hash"] != calculated:
                return {
                    "status": "tampered",
                    "error": f"Datos alterados en factura {row['invoice_number']}. Hash calculado: {calculated}, encontrado en BD: {row['current_hash']}"
                }
            expected_prev_hash = row["current_hash"]

        return {
            "status": "valid",
            "message": f"Integridad validada con éxito. Se verificaron {len(rows)} facturas sin alteraciones."
        }
