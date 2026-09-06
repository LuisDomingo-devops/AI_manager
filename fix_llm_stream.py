import os
llm_client_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\infrastructure\adapters\llm_client.py'

with open(llm_client_path, 'r', encoding='utf-8') as f:
    content = f.read()

stream_method = """
    async def stream_chat(self, messages: list[dict[str, str]], **kwargs):
        \"\"\"Envía un listado completo de mensajes al modelo de lenguaje y devuelve un generador asíncrono (SSE).\"\"\"
        anonymized_messages = messages
        if settings.ANONYMIZE_LLM_CALLS:
            from app.utils.anonymizer import DataAnonymizer
            anonymizer = DataAnonymizer()
            anonymized_messages = []
            for msg in messages:
                anonymized_messages.append({"role": msg.get("role"), "content": anonymizer.anonymize(msg.get("content", ""))[0]})

        model_name = settings.GEMINI_MODEL_NAME

        if settings.GEMINI_PROXY_URL:
            # Asumimos que el proxy soporta stream enviando una flag o passthrough
            url = settings.GEMINI_PROXY_URL
            headers = {"X-Alfonso-License-Token": settings.ALFONSO_CLIENT_SECRET}
            contents = []
            for msg in anonymized_messages:
                role = "model" if msg.get("role") == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})
                
            payload = {
                "contents": contents,
                "model": model_name,
                "apiVersion": settings.GEMINI_API_VERSION,
                "stream": True # Flag para el worker
            }
            
            # Usar streaming de httpx
            import httpx
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    yield f"Error: {response.status_code}"
                    return
                async for chunk in response.aiter_text():
                    if chunk:
                        yield chunk
        else:
            # Fallback a Ollama stream
            payload = {
                "model": model_name,
                "messages": anonymized_messages,
                "stream": True,
                "keep_alive": -1,
            }
            async with client.stream("POST", f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            data = json.loads(line)
                            yield data.get("message", {}).get("content", "")
                        except:
                            pass
"""

if "def stream_chat(" not in content:
    # Insert after `async def chat(` method finishes. Let's just put it before `async def generate(`
    content = content.replace("    async def generate(", stream_method + "\n    async def generate(")
    with open(llm_client_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("llm_client.py updated with stream_chat")
else:
    print("stream_chat already exists.")
