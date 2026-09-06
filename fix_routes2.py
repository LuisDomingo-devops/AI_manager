import os

routes_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\api\routes.py'

with open(routes_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Already added stream: bool = False
if "def chat_endpoint" in content:
    # We will just replace the core of the endpoint to use stream if True
    old_block = """    with Timer() as t:
        result = await orchestrator.run(
            req.message,
            llm,
            request_id=request_id,
            session_id=session_id,
            client_id=client_id,
        )

    status = result.get("type", "unknown")"""
    
    new_block = """    if getattr(req, "stream", False):
        async def event_stream():
            try:
                import json
                async for chunk in orchestrator.run_stream(
                    req.message,
                    llm,
                    request_id=request_id,
                    session_id=session_id,
                    client_id=client_id,
                ):
                    yield f"data: {chunk}\\n\\n"
                yield "data: [DONE]\\n\\n"
            except Exception as e:
                import json
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\\n\\n"
        return StreamingResponse(event_stream(), media_type="text/event-stream")

    with Timer() as t:
        result = await orchestrator.run(
            req.message,
            llm,
            request_id=request_id,
            session_id=session_id,
            client_id=client_id,
        )

    status = result.get("type", "unknown")"""

    content = content.replace(old_block, new_block)
    with open(routes_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("routes.py updated with streaming logic in POST /chat")
