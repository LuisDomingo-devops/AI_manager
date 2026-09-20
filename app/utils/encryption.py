import os
import base64
import hashlib
from pathlib import Path

import keyring

KEY_PATH = Path(__file__).resolve().parents[2] / "data" / ".key"

def get_or_create_key() -> bytes:
    from app.utils.logger import error_logger, app_logger
    # 0. Intentar obtener la clave desde la configuración (archivo .env / settings)
    try:
        from app.config import settings
        if settings.DATABASE_ENCRYPTION_KEY:
            key_str = settings.DATABASE_ENCRYPTION_KEY.strip()
            # Si tiene longitud base64 de 32 bytes decodificada (44 caracteres)
            try:
                decoded = base64.b64decode(key_str.encode('utf-8'))
                if len(decoded) == 32:
                    return decoded
            except Exception as e:
                error_logger.exception(f"Error al decodificar DATABASE_ENCRYPTION_KEY como base64: {e}")
            # Fallback si no es base64 de 32 bytes directo: derivar con SHA-256
            return hashlib.sha256(key_str.encode('utf-8')).digest()
    except Exception as e:
        error_logger.exception(f"Error al acceder a settings.DATABASE_ENCRYPTION_KEY: {e}")

    # 1. Intentar obtener la clave desde el Keyring del sistema
    try:
        stored_key_b64 = keyring.get_password("alfonso_autonomo", "db_encryption_key")
        if stored_key_b64:
            # Eliminar archivo local sobrante de instalaciones anteriores
            if KEY_PATH.exists():
                try:
                    KEY_PATH.unlink()
                except Exception as e:
                    error_logger.exception(f"Error al eliminar KEY_PATH local: {e}")
            return base64.b64decode(stored_key_b64.encode('utf-8'))
    except Exception as e:
        error_logger.exception(f"Error al leer la clave del keyring: {e}")

    # 2. Si no está en el Keyring, comprobar el archivo de clave local como fallback
    if KEY_PATH.exists():
        try:
            return KEY_PATH.read_bytes()
        except Exception as e:
            error_logger.exception(f"Error al leer KEY_PATH local: {e}")

    # 3. Verificación de seguridad (Fail-Closed por defecto)
    alfonso_env = os.getenv("ALFONSO_ENV", "production").strip().lower()
    if alfonso_env not in ["development", "local", "test"]:
        raise RuntimeError(
            f"FATAL: Entorno configurado como '{alfonso_env}'. "
            "No se ha configurado 'DATABASE_ENCRYPTION_KEY'. "
            "En entornos no-desarrollo está terminantemente prohibido generar claves de cifrado temporales en memoria "
            "debido al riesgo crítico de pérdida permanente de acceso a datos cifrados tras reinicio del servicio. "
            "Por favor, configure la variable de entorno DATABASE_ENCRYPTION_KEY con una clave base64 válida de 32 bytes."
        )

    # 4. Generar nueva clave y advertir en los logs (solo permitido en desarrollo/local)
    new_key = os.urandom(32)
    try:
        new_key_b64 = base64.b64encode(new_key).decode('utf-8')
        app_logger.warning(
            "⚠️ ALERTA DE SEGURIDAD: Se ha generado una clave de cifrado temporal de desarrollo. "
            "Para un despliegue portable y seguro en producción, añade la siguiente clave "
            "a tu archivo .env como DATABASE_ENCRYPTION_KEY:\n%s", new_key_b64
        )
    except Exception as e:
        error_logger.exception(f"Error al loggear la nueva clave: {e}")
    
    # 4. Intentar guardar en el Keyring del sistema
    saved_in_keyring = False
    try:
        new_key_b64 = base64.b64encode(new_key).decode('utf-8')
        keyring.set_password("alfonso_autonomo", "db_encryption_key", new_key_b64)
        saved_in_keyring = True
    except Exception as e:
        error_logger.exception(f"Error al guardar la clave en el keyring: {e}")
        
    # 5. Si falló el keyring, guardar en archivo local
    if not saved_in_keyring:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            KEY_PATH.write_bytes(new_key)
        except Exception as e:
            error_logger.exception(f"Error al escribir la clave en KEY_PATH local: {e}")
            
    return new_key

class DatabaseEncryptor:
    def __init__(self):
        self.raw_key = get_or_create_key()
        try:
            from cryptography.fernet import Fernet
            # Fernet requiere una clave de 32 bytes codificada en base64 urlsafe
            b64_key = base64.urlsafe_b64encode(self.raw_key)
            self.fernet = Fernet(b64_key)
        except ImportError as e:
            raise ImportError(
                "La librería 'cryptography' es requerida para el funcionamiento seguro de Alfonso Autónomo. "
                "Por favor, instala las dependencias usando 'pip install -r requirements.txt'."
            ) from e

    def encrypt(self, plain_text: str) -> str:
        if plain_text is None:
            return None
        if not isinstance(plain_text, str):
            plain_text = str(plain_text)
            
        data = plain_text.encode('utf-8')
        try:
            return self.fernet.encrypt(data).decode('utf-8')
        except Exception as e:
            raise RuntimeError("Error al cifrar el campo de base de datos.") from e

    def decrypt(self, cipher_text: str) -> str:
        if cipher_text is None:
            return None
        if not isinstance(cipher_text, str):
            return str(cipher_text)
            
        try:
            return self.fernet.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Fallo al descifrar el texto: {e}") from e


encryptor = DatabaseEncryptor()

