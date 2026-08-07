import os
import base64
import hashlib
from pathlib import Path

import keyring

KEY_PATH = Path(__file__).resolve().parents[2] / "data" / ".key"

def get_or_create_key() -> bytes:
    # 1. Intentar obtener la clave desde el Keyring del sistema
    try:
        stored_key_b64 = keyring.get_password("alfonso_autonomo", "db_encryption_key")
        if stored_key_b64:
            # Eliminar archivo local sobrante de instalaciones anteriores
            if KEY_PATH.exists():
                try:
                    KEY_PATH.unlink()
                except Exception:
                    pass
            return base64.b64decode(stored_key_b64.encode('utf-8'))
    except Exception:
        pass

    # 2. Si no está en el Keyring, comprobar el archivo de clave local como fallback
    if KEY_PATH.exists():
        try:
            return KEY_PATH.read_bytes()
        except Exception:
            pass

    # 3. Generar nueva clave
    new_key = os.urandom(32)
    
    # 4. Intentar guardar en el Keyring del sistema
    saved_in_keyring = False
    try:
        new_key_b64 = base64.b64encode(new_key).decode('utf-8')
        keyring.set_password("alfonso_autonomo", "db_encryption_key", new_key_b64)
        saved_in_keyring = True
    except Exception:
        pass
        
    # 5. Si falló el keyring, guardar en archivo local
    if not saved_in_keyring:
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        try:
            KEY_PATH.write_bytes(new_key)
        except Exception:
            pass
            
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
            if cipher_text.startswith("gAAAA"):
                raise RuntimeError("Error crítico al descifrar un dato corrupto o clave incorrecta.") from e
            # En caso de error (texto plano o cifrado fallback antiguo), devolver la cadena original
            return cipher_text


encryptor = DatabaseEncryptor()

