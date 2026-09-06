import re
routes_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\api\routes.py'

with open(routes_path, 'r', encoding='utf-8') as f:
    content = f.read()

if "stream: bool" not in content:
    content = content.replace(
        "class ChatRequest(BaseModel):\n    message: str\n    session_id: str",
        "class ChatRequest(BaseModel):\n    message: str\n    session_id: str\n    stream: bool = False"
    )

if "StreamingResponse" not in content:
    content = content.replace("from fastapi import APIRouter", "from fastapi import APIRouter\nfrom fastapi.responses import StreamingResponse")
    content = content.replace("from starlette.responses import HTMLResponse", "from starlette.responses import HTMLResponse, StreamingResponse")

# Let's find chat_endpoint and replace it
# Wait, I'll just write a script to patch it dynamically.

patch = """
    if req.stream:
        # Modo Streaming
        async def event_stream():
            try:
                import json
                async for chunk in planner.stream_process_user_message(req.message, req.session_id, request_id):
                    # Formato SSE
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\\n\\n"
                yield "data: [DONE]\\n\\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")
"""

# I need to know how chat_endpoint looks like to inject this.
