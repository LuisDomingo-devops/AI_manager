"""
CONFIG — Configuración global de la aplicación.

¿QUÉ HACE?
Define y expone la clase Settings cargando variables de entorno, nombres de modelos de IA y rutas de prompts utilizando pydantic_settings.

¿CUÁNDO LO HACE?
Al inicializar la aplicación para configurar la dirección de Ollama, el modelo cargado y demás constantes clave de Alfonso.

¿CÓMO LO HACE?
Heredando de BaseSettings para realizar validación estricta de tipos y leer opcionalmente archivos .env.

¿CON QUÉ OTROS SCRIPTS ESTÁ RELACIONADO?
- app/main.py (consume los settings para inicializar FastAPI y los servicios)
- app/adapters/llm_client.py (utiliza la URL de Ollama y el nombre del modelo)
"""

import json
from pathlib import Path
from typing import Any, Dict
from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    MODEL_NAME: str = "qwen2.5:1.5b"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL_NAME: str = "gemini-3.1-flash-lite"
    GEMINI_API_VERSION: str = "v1beta"

    ANONYMIZE_LLM_CALLS: bool = True

    DATABASE_ENCRYPTION_KEY: str = ""

    ALFONSO_API_KEY: str = ""
    ALFONSO_BRIDGE_TOKEN: str = ""
    VERIFACTU_ACTIVE: bool = True
    ALFONSO_SIF_PRODUCER_NIF: str = "B12345678"
    ALFONSO_AEAT_URL: str = ""
    ALFONSO_CLIENT_TOKENS: str = ""  # Formato JSON: {"client_id1": "token1", "client_id2": "token2"} o client1:token1,client2:token2
    ALFONSO_CLIENT_ROLES: str = ""   # Formato JSON: {"client_id1": "admin", "client_id2": "guest"} o client1:admin,client2:guest

    ALFONSO_USER_NAME: str = "Luis Domingo"
    ALFONSO_USER_EMAIL: str = ""
    ALFONSO_USER_PHONE: str = "+34 600 000 000"
    ALFONSO_USER_NIF: str = ""

    # ── Credenciales Open Banking PSD2 (GoCardless / Nordigen) ─────────
    GOCARDLESS_SECRET_ID: str = ""
    GOCARDLESS_SECRET_KEY: str = ""

    CHAT_PROMPT_PATH: str = "app/prompts/chat_system.txt"

    # ── Datos de Certificación SIF (Veri*Factu) ────────────────────────
    SIF_DEVELOPER: str = "Alfonso S.L."
    SIF_SOFTWARE_NAME: str = "Alfonso Autónomo SIF"
    SIF_VERSION: str = "2.0.0"
    SIF_REGULATION: str = "Real Decreto 1007/2023 y Orden HAC/1177/2024"
    SIF_CERTIFIED_DATE: str = "2026-08-07"

    # ── Parámetros de inferencia ──────────────────────────────────────
    LLM_NUM_CTX_TOOL: int = 1024
    LLM_NUM_CTX_CHAT: int = 2048
    LLM_TIMEOUT: int = 300
    LLM_IS_REASONING: bool = False

    BRIDGE_HOST: str = "127.0.0.1"
    BRIDGE_PORT: int = 8765
    BRIDGE_TIMEOUT: int = 30

    TOOL_VALIDATION_MODE: str = "strict"

    # ── Memoria Vectorial (Fase 4) ──────────────────────────────────
    CHROMA_DB_PATH: str = "data/chroma"
    EMBEDDING_MODEL_NAME: str = "nomic-embed-text"

    # ── VALIDADOR ULTRA-ROBUSTO ANTE COMENTARIOS CACHEADOS ────────────
    @model_validator(mode="before")
    @classmethod # Este decorador asegura que la limpieza de comentarios se aplique
                 # antes de la validación de Pydantic y esto es crucial para evitar
                 # errores de parsing en cadenas con comentarios inline.
    def clean_all_inline_comments(cls, data: Any) -> Any:
        """
        Limpia los comentarios inline de cualquier variable cargada,
        evitando que cadenas como 'true # comentario' rompan Pydantic.
        """
        if isinstance(data, dict):
            cleaned: Dict[str, Any] = {}
            for key, value in data.items():
                if isinstance(value, str):
                    # Divide por el hash y elimina espacios en blanco restantes
                    cleaned[key] = value.split("#")[0].strip()
                else:
                    cleaned[key] = value
            return cleaned
        return data

    def get_client_token(self, client_id: str) -> str | None:
        if not self.ALFONSO_CLIENT_TOKENS:
            return None
        try:
            tokens = json.loads(self.ALFONSO_CLIENT_TOKENS)
            return tokens.get(client_id)
        except Exception:
            for item in self.ALFONSO_CLIENT_TOKENS.split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    if k.strip() == client_id:
                        return v.strip()
            return None

    def get_client_role(self, client_id: str) -> str:
        if not self.ALFONSO_CLIENT_ROLES:
            return "guest"
        try:
            roles = json.loads(self.ALFONSO_CLIENT_ROLES)
            return roles.get(client_id, "guest")
        except Exception:
            for item in self.ALFONSO_CLIENT_ROLES.split(","):
                if ":" in item:
                    k, v = item.split(":", 1)
                    if k.strip() == client_id:
                        return v.strip()
            return "guest"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

# Asegurar la presencia de credenciales seguras de forma persistente y compartida
import secrets
from pathlib import Path

data_dir = Path(__file__).resolve().parent.parent / "data"
data_dir.mkdir(parents=True, exist_ok=True)

api_key_file = data_dir / ".api_key"
bridge_token_file = data_dir / ".bridge_token"

if not settings.ALFONSO_API_KEY or settings.ALFONSO_API_KEY.strip() == "":
    if api_key_file.exists():
        settings.ALFONSO_API_KEY = api_key_file.read_text(encoding="utf-8").strip()
    else:
        settings.ALFONSO_API_KEY = secrets.token_hex(32)
        api_key_file.write_text(settings.ALFONSO_API_KEY, encoding="utf-8")

if not settings.ALFONSO_BRIDGE_TOKEN or settings.ALFONSO_BRIDGE_TOKEN.strip() == "":
    if bridge_token_file.exists():
        settings.ALFONSO_BRIDGE_TOKEN = bridge_token_file.read_text(encoding="utf-8").strip()
    else:
        settings.ALFONSO_BRIDGE_TOKEN = secrets.token_hex(32)
        bridge_token_file.write_text(settings.ALFONSO_BRIDGE_TOKEN, encoding="utf-8")
