import re
path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\infrastructure\adapters\llm_client.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace settings.GEMINI_API_KEY or settings.GEMINI_PROXY_URL with just settings.GEMINI_PROXY_URL
content = content.replace("settings.GEMINI_API_KEY or settings.GEMINI_PROXY_URL", "settings.GEMINI_PROXY_URL")

# Find the block where it does:
#         if settings.GEMINI_PROXY_URL:
#             url = settings.GEMINI_PROXY_URL
#             headers["X-Alfonso-License-Token"] = settings.ALFONSO_CLIENT_SECRET
#             payload["model"] = settings.GEMINI_MODEL_NAME
#             payload["apiVersion"] = settings.GEMINI_API_VERSION
#         else:
#             url = f"https://generativelanguage.googleapis.com/{settings.GEMINI_API_VERSION}/models/{settings.GEMINI_MODEL_NAME}:generateContent?key={settings.GEMINI_API_KEY}"

# Replace with strict proxy requirement for generate()
old_generate = '''        if settings.GEMINI_PROXY_URL:
            url = settings.GEMINI_PROXY_URL
            headers["X-Alfonso-License-Token"] = settings.ALFONSO_CLIENT_SECRET
            payload["model"] = settings.GEMINI_MODEL_NAME
            payload["apiVersion"] = settings.GEMINI_API_VERSION
        else:
            url = f"https://generativelanguage.googleapis.com/{settings.GEMINI_API_VERSION}/models/{settings.GEMINI_MODEL_NAME}:generateContent?key={settings.GEMINI_API_KEY}"'''

new_generate = '''        if not settings.GEMINI_PROXY_URL:
            raise RuntimeError("GEMINI_PROXY_URL no está configurado. La conexión directa a la API no está permitida.")
        
        url = settings.GEMINI_PROXY_URL
        headers["X-Alfonso-License-Token"] = settings.ALFONSO_CLIENT_SECRET
        payload["model"] = settings.GEMINI_MODEL_NAME
        payload["apiVersion"] = settings.GEMINI_API_VERSION'''

content = content.replace(old_generate, new_generate)

# Similarly for chat()
old_chat = '''        if settings.GEMINI_PROXY_URL:
            url = settings.GEMINI_PROXY_URL
            headers["X-Alfonso-License-Token"] = settings.ALFONSO_CLIENT_SECRET
            payload["model"] = settings.GEMINI_MODEL_NAME
            payload["apiVersion"] = settings.GEMINI_API_VERSION
        else:
            url = f"https://generativelanguage.googleapis.com/{settings.GEMINI_API_VERSION}/models/{settings.GEMINI_MODEL_NAME}:generateContent?key={settings.GEMINI_API_KEY}"'''

content = content.replace(old_chat, new_generate) # They are identical

# Fix the RuntimeError message that had GEMINI_API_KEY
content = content.replace('"GEMINI_API_KEY o GEMINI_PROXY_URL no están configurados."', '"GEMINI_PROXY_URL no está configurado."')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
