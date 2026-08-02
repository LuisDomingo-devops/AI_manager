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
        self.fernet = None
        try:
            from cryptography.fernet import Fernet
            # Fernet requiere una clave de 32 bytes codificada en base64 urlsafe
            b64_key = base64.urlsafe_b64encode(self.raw_key)
            self.fernet = Fernet(b64_key)
        except ImportError:
            pass

    def encrypt(self, plain_text: str) -> str:
        if plain_text is None:
            return None
        if not isinstance(plain_text, str):
            plain_text = str(plain_text)
            
        data = plain_text.encode('utf-8')
        if self.fernet:
            try:
                return self.fernet.encrypt(data).decode('utf-8')
            except Exception:
                pass
        
        # Fallback de cifrado simétrico en Python puro (XOR + keystream derivado de SHA-256 con IV)
        iv = os.urandom(16)
        keystream = b""
        counter = 0
        while len(keystream) < len(data):
            h = hashlib.sha256(self.raw_key + iv + str(counter).encode('utf-8')).digest()
            keystream += h
            counter += 1
        
        encrypted_bytes = bytes(b ^ k for b, k in zip(data, keystream))
        result_bytes = iv + encrypted_bytes
        return "fallback_" + base64.b64encode(result_bytes).decode('utf-8')

    def decrypt(self, cipher_text: str) -> str:
        if cipher_text is None:
            return None
        if not isinstance(cipher_text, str):
            return str(cipher_text)
            
        if self.fernet and not cipher_text.startswith("fallback_"):
            try:
                return self.fernet.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
            except Exception:
                pass
        
        raw_cipher = cipher_text
        if raw_cipher.startswith("fallback_"):
            raw_cipher = raw_cipher[len("fallback_"):]
            
        try:
            decoded = base64.b64decode(raw_cipher.encode('utf-8'))
            if len(decoded) < 16:
                return cipher_text
            iv = decoded[:16]
            encrypted_bytes = decoded[16:]
            
            keystream = b""
            counter = 0
            while len(keystream) < len(encrypted_bytes):
                h = hashlib.sha256(self.raw_key + iv + str(counter).encode('utf-8')).digest()
                keystream += h
                counter += 1
                
            decrypted_bytes = bytes(b ^ k for b, k in zip(encrypted_bytes, keystream))
            return decrypted_bytes.decode('utf-8')
        except Exception:
            return cipher_text

encryptor = DatabaseEncryptor()
