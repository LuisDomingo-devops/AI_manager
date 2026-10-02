"""
Servicio Oficial de Registro y Auditoría del SIF (sif_event_log).
Conforme al Artículo 8 de la Orden HAC/1177/2024 y RD 1007/2023.
"""

import base64
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.domain.exceptions import SIFEventLogCorruptedError, SIFAuditWriteError
from app.infrastructure.database.legal_connection import legal_read_transaction, legal_write_transaction
from app.utils.logger import app_logger


class SIFAuditLogger:
    """
    Gestor del Libro de Eventos del Sistema Informático de Facturación (SIF).
    Garantiza inalterabilidad, encadenamiento SHA-256 y firma digital en sif_event_log.
    """

    _private_key_path = Path("data/certs/sif_audit_key.pem")
    _cached_key: Optional[rsa.RSAPrivateKey] = None

    @classmethod
    def get_or_create_private_key(cls) -> rsa.RSAPrivateKey:
        """Obtiene o genera la clave privada RSA para firmar los eventos del SIF."""
        if cls._cached_key is not None:
            return cls._cached_key

        cls._private_key_path.parent.mkdir(parents=True, exist_ok=True)
        if cls._private_key_path.exists():
            try:
                with open(cls._private_key_path, "rb") as key_file:
                    cls._cached_key = serialization.load_pem_private_key(
                        key_file.read(),
                        password=None
                    )
                    return cls._cached_key
            except Exception as e:
                app_logger.warning("No se pudo cargar clave privada SIF existente, generando nueva: %s", e)

        # Generar clave RSA 2048 bits
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        try:
            pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            with open(cls._private_key_path, "wb") as key_file:
                key_file.write(pem)
        except Exception as e:
            app_logger.warning("No se pudo persistir clave privada SIF en disco: %s", e)

        cls._cached_key = key
        return cls._cached_key

    def registrar_evento(
        self,
        tenant_id: str,
        tipo_evento: str,
        descripcion: str,
        detalles_adicionales: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Inserta un evento reglamentario en sif_event_log:
        1. Consulta transaccionalmente el último hash de evento del tenant.
        2. Concatena: tipo_evento | descripcion | timestamp | prev_event_hash.
        3. Calcula el hash SHA-256 en mayúsculas.
        4. Firma el hash digitalmente con RSA-SHA256 PKCS1v15.
        5. Persiste atómicamente y retorna el current_hash.
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()
            key = self.get_or_create_private_key()

            with legal_write_transaction(client_id=tenant_id) as conn:
                cursor = conn.cursor()
                row = cursor.execute(
                    "SELECT current_hash FROM sif_event_log WHERE tenant_id = ? ORDER BY id DESC LIMIT 1",
                    (tenant_id,)
                ).fetchone()
                prev_hash = row[0] if row else None

                ph = prev_hash or ""
                concat_str = f"{tipo_evento}|{descripcion}|{timestamp}|{ph}"
                current_hash = hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()

                # Firma digital
                sig_bytes = key.sign(
                    current_hash.encode("utf-8"),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                signature_b64 = base64.b64encode(sig_bytes).decode("utf-8")

                cursor.execute("""
                    INSERT INTO sif_event_log (
                        tenant_id, event_type, description, prev_event_hash, current_hash, signature, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (tenant_id, tipo_evento, descripcion, prev_hash, current_hash, signature_b64, timestamp))

            return current_hash
        except Exception as e:
            app_logger.error("Error al registrar evento en sif_event_log: %s", str(e))
            raise SIFAuditWriteError(message=f"Fallo registrando evento SIF: {e}")

    def verificar_integridad_eventos(self, tenant_id: str, raise_on_error: bool = False) -> bool:
        """
        Verifica de principio a fin el encadenamiento criptográfico y firmas digitales de sif_event_log.
        """
        key = self.get_or_create_private_key()
        pub_key = key.public_key()

        with legal_read_transaction(client_id=tenant_id) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, event_type, description, prev_event_hash, current_hash, signature, created_at "
                "FROM sif_event_log WHERE tenant_id = ? ORDER BY id ASC",
                (tenant_id,)
            ).fetchall()

        if not rows:
            return True

        prev_expected_hash = None

        for idx, row in enumerate(rows):
            r_id = row["id"]
            r_type = row["event_type"]
            r_desc = row["description"]
            r_prev_hash = row["prev_event_hash"]
            r_curr_hash = row["current_hash"]
            r_sig = row["signature"]
            r_created = row["created_at"]

            # 1. Comprobar encadenamiento
            if idx == 0:
                if r_prev_hash is not None:
                    if raise_on_error:
                        raise SIFEventLogCorruptedError(f"Evento génesis con ID {r_id} tiene prev_event_hash no nulo")
                    return False
            else:
                if r_prev_hash != prev_expected_hash:
                    if raise_on_error:
                        raise SIFEventLogCorruptedError(f"Ruptura de cadena en evento ID {r_id}: esperado {prev_expected_hash}, obtenido {r_prev_hash}")
                    return False

            # 2. Recalcular hash
            ph = r_prev_hash or ""
            concat_str = f"{r_type}|{r_desc}|{r_created}|{ph}"
            recomputed = hashlib.sha256(concat_str.encode("utf-8")).hexdigest().upper()
            if recomputed != r_curr_hash:
                if raise_on_error:
                    raise SIFEventLogCorruptedError(f"Hash recalculado no coincide en evento ID {r_id}")
                return False

            # 3. Validar firma digital
            try:
                sig_bytes = base64.b64decode(r_sig)
                pub_key.verify(
                    sig_bytes,
                    r_curr_hash.encode("utf-8"),
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
            except Exception as e:
                if raise_on_error:
                    raise SIFEventLogCorruptedError(f"Firma digital inválida en evento ID {r_id}: {e}")
                return False

            prev_expected_hash = r_curr_hash

        return True

    def exportar_libro_eventos(self, tenant_id: str) -> List[Dict[str, Any]]:
        """
        Exporta el libro de eventos en formato estructurado para auditoría tributaria.
        """
        with legal_read_transaction(client_id=tenant_id) as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                "SELECT id, tenant_id, event_type, description, prev_event_hash, current_hash, signature, created_at "
                "FROM sif_event_log WHERE tenant_id = ? ORDER BY id ASC",
                (tenant_id,)
            ).fetchall()

        return [
            {
                "id": r["id"],
                "tenant_id": r["tenant_id"],
                "event_type": r["event_type"],
                "description": r["description"],
                "prev_event_hash": r["prev_event_hash"],
                "current_hash": r["current_hash"],
                "signature": r["signature"],
                "created_at": r["created_at"]
            }
            for r in rows
        ]
