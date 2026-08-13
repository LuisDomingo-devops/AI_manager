import os
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
from app.adapters.memory.memory import _get_connection, tenant_context, DB_PATH, IS_TESTING
from app.utils.encryption import encryptor

class BackupService:
    HEADER = b"ALFONSO_BACKUP_v1"

    @classmethod
    def get_db_path(cls, client_id: str = None) -> Path:
        """Resuelve la ruta física de la base de datos para el inquilino."""
        cid = (client_id or tenant_context.get()).strip().lower()
        if IS_TESTING:
            if cid == "default":
                return DB_PATH
            return DB_PATH.parent / f"test_memory_{cid}.db"
        return DB_PATH.parent / f"memory_{cid}.db"

    @classmethod
    def export_backup(cls, client_id: str = None) -> bytes:
        """
        Genera un backup cifrado y firmado digitalmente de la base de datos del tenant actual.
        """
        db_path = cls.get_db_path(client_id)
        if not db_path.exists():
            raise FileNotFoundError(f"No existe base de datos para el tenant en la ruta {db_path}")

        # 1. Asegurar consistencia interna ejecutando un VACUUM
        conn = _get_connection(client_id)
        try:
            conn.execute("VACUUM")
            conn.commit()
        finally:
            conn.close()

        # 2. Leer los bytes de la base de datos
        db_bytes = db_path.read_bytes()

        # 3. Cifrar con Fernet usando la clave de seguridad del keyring
        encrypted_bytes = encryptor.fernet.encrypt(db_bytes)

        # 4. Firmar digitalmente con HMAC-SHA256 usando la clave en crudo del keyring
        signature = hmac.new(encryptor.raw_key, encrypted_bytes, hashlib.sha256).digest()

        # 5. Estructurar el backup final
        backup_data = cls.HEADER + signature + encrypted_bytes
        return backup_data

    @classmethod
    def restore_backup(cls, backup_bytes: bytes, client_id: str = None) -> bool:
        """
        Restaura una copia de seguridad cifrada, verificando la firma digital antes de aplicarla.
        """
        # 1. Validar cabecera del formato de backup
        if not backup_bytes.startswith(cls.HEADER):
            raise ValueError("Formato de backup inválido: cabecera incorrecta")

        header_len = len(cls.HEADER)
        sig_len = 32  # SHA256 produce 32 bytes

        if len(backup_bytes) < header_len + sig_len:
            raise ValueError("Datos de backup incompletos o corruptos")

        # 2. Extraer firma y datos cifrados
        extracted_sig = backup_bytes[header_len : header_len + sig_len]
        encrypted_bytes = backup_bytes[header_len + sig_len :]

        # 3. Verificar firma HMAC-SHA256 para integridad y autenticidad
        expected_sig = hmac.new(encryptor.raw_key, encrypted_bytes, hashlib.sha256).digest()
        if not hmac.compare_digest(extracted_sig, expected_sig):
            raise ValueError("Firma del backup inválida o archivo alterado (Keyring o datos no coinciden)")

        # 4. Descifrar base de datos
        try:
            decrypted_db_bytes = encryptor.fernet.decrypt(encrypted_bytes)
        except Exception as e:
            raise ValueError("Error al descifrar el backup (clave incorrecta o datos corruptos)") from e

        # 5. Sobrescribir el archivo de base de datos
        db_path = cls.get_db_path(client_id)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Escribir a un archivo temporal primero y luego renombrar para evitar cierres corruptos
        temp_path = db_path.with_suffix(".tmp")
        try:
            temp_path.write_bytes(decrypted_db_bytes)
            if db_path.exists():
                os.remove(db_path)
            os.rename(temp_path, db_path)
        except Exception as e:
            if temp_path.exists():
                try:
                    os.unlink(temp_path)
                except Exception:
                    pass
            raise RuntimeError(f"Error escribiendo el archivo de base de datos: {e}") from e

        return True
