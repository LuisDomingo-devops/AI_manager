import os
import hmac
import hashlib
from datetime import datetime
from pathlib import Path
from app.adapters.memory.memory import _get_connection, tenant_context
from app.infrastructure.database import connection_manager
from app.utils.encryption import encryptor

class BackupService:
    HEADER = b"ALFONSO_BACKUP_v1"

    @classmethod
    def get_db_path(cls, client_id: str = None) -> Path:
        """Resuelve la ruta física de la base de datos para el inquilino."""
        cid = (client_id or tenant_context.get()).strip().lower()
        
        # Handle string URIs safely (like "file:main_mem") for testing
        db_path_val = connection_manager.DB_PATH
        if connection_manager.IS_TESTING and isinstance(db_path_val, str):
            base_path = Path("data/memory.db")
        else:
            base_path = Path(str(db_path_val))
            
        if connection_manager.IS_TESTING:
            if cid == "default":
                return base_path
            return base_path.parent / f"test_memory_{cid}.db"
        
        if cid == "default":
            return base_path
        return base_path.parent / f"memory_{cid}.db"

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
                    from app.utils.logger import error_logger
                    error_logger.warning("Excepción genérica interceptada silenciosamente.")
            raise RuntimeError(f"Error escribiendo el archivo de base de datos: {e}") from e

        return True

    @classmethod
    def create_daily_backup(cls, client_id: str = "default") -> None:
        """
        Método programado para generar la copia de seguridad y persistirla en el disco 
        para tareas de mantenimiento en background.
        """
        try:
            backup_data = cls.export_backup(client_id)
            backup_dir = Path("data/backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"backup_{client_id}_{timestamp}.enc"
            backup_file.write_bytes(backup_data)
            from app.utils.logger import app_logger
            app_logger.info(f"Backup programado creado exitosamente: {backup_file}")
            
            # Limpieza de backups antiguos (retención: 7 días)
            from datetime import timedelta
            now = datetime.now()
            for f in backup_dir.glob(f"backup_{client_id}_*.enc"):
                if f.is_file():
                    try:
                        time_str = f.stem.split("_")[-2:]
                        file_time = datetime.strptime(f"{time_str[0]}_{time_str[1]}", "%Y%m%d_%H%M%S")
                        if now - file_time > timedelta(days=7):
                            f.unlink()
                            app_logger.info(f"Backup antiguo eliminado: {f}")
                    except Exception as e:
                        app_logger.warning(f"Error procesando limpieza de {f}: {e}")
        except Exception as e:
            from app.utils.logger import error_logger
            error_logger.error(f"Error crítico creando backup diario para {client_id}: {str(e)}")
