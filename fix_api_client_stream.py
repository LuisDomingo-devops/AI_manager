import os

api_client_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\client\core\api_client.py'
with open(api_client_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace send_chat to support stream=False (default behavior) or stream=True (returns generator)
old_send_chat = """    def send_chat(self, message: str, session_id: str) -> dict:"""
new_send_chat = """    def send_chat(self, message: str, session_id: str, stream: bool = False):"""

old_post_call = """        try:
            r = self.session.post(
                f"{self.base_url}/chat",
                json={
                    "message": message,
                    "client_info": {
                        "desktop_structure": desktop_structure,
                        "client_id": client_id
                    }
                },
                headers={"X-Session-ID": session_id},
                timeout=300,
            )
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"status": "error", "message": str(e)}"""

new_post_call = """        try:
            r = self.session.post(
                f"{self.base_url}/chat",
                json={
                    "message": message,
                    "stream": stream,
                    "client_info": {
                        "desktop_structure": desktop_structure,
                        "client_id": client_id
                    }
                },
                headers={"X-Session-ID": session_id},
                timeout=300,
                stream=stream
            )
            r.raise_for_status()
            if stream:
                def sse_generator():
                    import json
                    for line in r.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: "):
                                data_str = decoded_line[6:]
                                if data_str == "[DONE]":
                                    break
                                try:
                                    yield json.loads(data_str)
                                except:
                                    pass
                return sse_generator()
            return r.json()
        except Exception as e:
            if stream:
                return [{"type": "error", "message": str(e)}]
            return {"status": "error", "message": str(e)}"""

if "stream: bool = False" not in content:
    content = content.replace(old_send_chat, new_send_chat)
    content = content.replace(old_post_call, new_post_call)
    with open(api_client_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("api_client.py send_chat updated for SSE.")
