import asyncio
import sys
from pathlib import Path

# Configurar path del proyecto para poder importar app
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Cargar variables de entorno del archivo .env directamente
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")

from app.config import settings
from app.infrastructure.adapters.llm_client import OllamaClient

async def verify_connection():
    print("=== Iniciando Verificación de Conexión ===")
    print(f"Proxy URL: {settings.GEMINI_PROXY_URL}")
    print(f"Client Secret (primeros 5 caracteres): {settings.ALFONSO_CLIENT_SECRET[:5]}...")
    
    if not settings.GEMINI_PROXY_URL:
        print("[ERROR] GEMINI_PROXY_URL no está configurado en tu archivo .env.")
        return
        
    client = OllamaClient()
    
    try:
        print("\nEnviando prompt de prueba a través de tu Worker en Cloudflare...")
        # Enviar petición en modo chat
        respuesta = await client.generate(
            "¿Qué tiempo hace en Bilbao? (Puedes simular la respuesta o indicar que como modelo de lenguaje no tienes datos en tiempo real si es el caso)", 
            mode="chat"
        )
        print("\n[RESPUESTA RECIBIDA]:")
        print(f"-> {respuesta}\n")
        
        if "falló" in respuesta or "problemas técnicos" in respuesta:
            print("[ALERTA] La llamada devolvió una respuesta de fallback. Revisa los logs de Cloudflare o las credenciales.")
        else:
            print("[ÉXITO] La conexión y la inferencia a través de Cloudflare funcionan correctamente.")
            
    except Exception as e:
        print(f"\n[ERROR CRÍTICO] Ocurrió un fallo en la conexión: {e}")

if __name__ == "__main__":
    asyncio.run(verify_connection())
