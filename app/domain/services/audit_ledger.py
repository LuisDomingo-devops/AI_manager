import os
import hashlib
import base64
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from app.adapters.memory.memory import _get_connection
from app.utils.logger import app_logger
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes

class AuditLedgerService:
    _lock = threading.Lock()
    _private_key_path = Path(__file__).resolve().parents[3] / "data" / "keys" / "audit_ledger_private_key.pem"

    @classmethod
    def init_ledger_schema(cls) -> None:
        """Inicializa la tabla de log de auditoría inmutable si no existe."""
        with cls._lock:
            conn = _get_connection()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS audit_ledger_log (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        client_id       TEXT,
                        event_type      TEXT NOT NULL,
                        description     TEXT NOT NULL,
                        prev_hash       TEXT,
                        current_hash    TEXT NOT NULL,
                        signature       TEXT NOT NULL,
                        created_at      TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    @classmethod
    def get_or_create_private_key(cls) -> rsa.RSAPrivateKey:
        """Obtiene o crea la clave privada RSA para firmar los registros de auditoría."""
        cls._private_key_path.parent.mkdir(parents=True, exist_ok=True)
        if cls._private_key_path.exists():
            try:
                with open(cls._private_key_path, "r", encoding="utf-8") as key_file:
                    content = key_file.read().strip()
                return serialization.load_pem_private_key(
                    content.encode("utf-8"),
                    password=None
                )
            except Exception as e:
                app_logger.error(f"Error al leer clave privada de auditoría: {str(e)}")

        # Generar clave si no existe
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        try:
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(cls._private_key_path, "w", encoding="utf-8") as key_file:
                key_file.write(pem.decode("utf-8"))
        except Exception as e:
            app_logger.error(f"Error al guardar clave privada de auditoría: {str(e)}")
        return private_key

    @classmethod
    def get_last_ledger_hash(cls, client_id: str = None) -> Optional[str]:
        """Obtiene el hash del último registro en el ledger para un tenant."""
        cls.init_ledger_schema()
        conn = _get_connection()
        try:
            if client_id:
                row = conn.execute(
                    "SELECT current_hash FROM audit_ledger_log WHERE client_id = ? ORDER BY id DESC LIMIT 1",
                    (client_id,)
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT current_hash FROM audit_ledger_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
            return row["current_hash"] if row else None
        finally:
            conn.close()

    @classmethod
    def log_audit_event(cls, event_type: str, description: str, client_id: str = None) -> str:
        """
        Registra una acción crítica en el ledger inmutable calculando y
        encadenando hashes SHA-256 de forma criptográfica y firmándola localmente.
        """
        cls.init_ledger_schema()
        prev_hash = cls.get_last_ledger_hash(client_id)
        timestamp = datetime.now().isoformat()
        ph = prev_hash or ""
        cid = client_id or "global"
        
        # Generar contenido único para el hash
        concat_str = f"{cid}|{event_type}|{description}|{timestamp}|{ph}"
        current_hash = hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()
        
        # Firmar digitalmente
        private_key = cls.get_or_create_private_key()
        signature_bytes = private_key.sign(
            current_hash.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        signature_b64 = base64.b64encode(signature_bytes).decode("utf-8")
        
        conn = _get_connection()
        try:
            conn.execute("""
                INSERT INTO audit_ledger_log (
                    client_id, event_type, description, prev_hash, current_hash, signature, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cid, event_type, description, prev_hash, current_hash, signature_b64, timestamp))
            conn.commit()
        finally:
            conn.close()
            
        app_logger.info(f"Audit Ledger: registrado evento '{event_type}' ({current_hash})")
        return current_hash

    @classmethod
    def verify_ledger_integrity(cls, client_id: str = None) -> Dict[str, Any]:
        """
        Verifica la secuencia completa de hashes y firmas del Ledger de auditoría.
        Retorna el estado de validez del log.
        """
        cls.init_ledger_schema()
        query = "SELECT * FROM audit_ledger_log"
        params = []
        if client_id:
            query += " WHERE client_id = ?"
            params.append(client_id)
        query += " ORDER BY id ASC"

        conn = _get_connection()
        try:
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
            
        if not rows:
            return {"status": "valid", "message": "Ledger de auditoría vacío (sin registros)."}

        private_key = cls.get_or_create_private_key()
        public_key = private_key.public_key()
        calculated_prev_hash = ""

        for idx, row in enumerate(rows):
            cid = row["client_id"]
            event_type = row["event_type"]
            description = row["description"]
            prev_hash = row["prev_hash"] or ""
            current_hash = row["current_hash"]
            signature_b64 = row["signature"]
            timestamp = row["created_at"]

            # 1. Validar encadenamiento de hash anterior
            if prev_hash != calculated_prev_hash:
                return {
                    "status": "corrupted",
                    "message": f"Fallo de encadenamiento en registro ID {row['id']}. Esperado: {calculated_prev_hash}, Obtenido: {prev_hash}."
                }

            # 2. Recalcular hash para validar integridad de los datos
            concat_str = f"{cid}|{event_type}|{description}|{timestamp}|{prev_hash}"
            expected_hash = hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()
            if current_hash != expected_hash:
                return {
                    "status": "corrupted",
                    "message": f"Alteración de datos detectada en registro ID {row['id']}. Hash recalculado no coincide."
                }

            # 3. Verificar firma digital
            try:
                sig_bytes = base64.b64decode(signature_b64)
                public_key.verify(
                    sig_bytes,
                    current_hash.encode("utf-8"),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except Exception:
                return {
                    "status": "corrupted",
                    "message": f"Firma digital no válida en registro ID {row['id']}. Posible suplantación de identidad."
                }

            calculated_prev_hash = current_hash

        return {
            "status": "valid",
            "message": f"Integridad del Ledger validada exitosamente. Se verificaron {len(rows)} registros sin alteraciones."
        }
