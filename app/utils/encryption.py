import os
import base64
import hashlib
from pathlib import Path

KEY_PATH = Path(__file__).resolve().parents[2] / "data" / ".key"

def get_or_create_key() -> bytes:
    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if KEY_PATH.exists():
        try:
            return KEY_PATH.read_bytes()
        except Exception:
            pass
    # Generar nueva clave
    new_key = os.urandom(32)
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
        except Exception:
            # En caso de error (texto plano, datos corruptos o cifrado fallback antiguo), devolver la cadena original
            return cipher_text


encryptor = DatabaseEncryptor()

