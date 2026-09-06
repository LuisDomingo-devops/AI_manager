import os
import re

orchestrator_path = r'c:\Users\luisd\Desktop\Alfonso_Autonomo\app\domain\planner_orchestrator.py'

with open(orchestrator_path, 'r', encoding='utf-8') as f:
    content = f.read()

stream_method = """
    async def run_stream(self, user_message, llm=None, request_id=None, session_id=None, client_id=None):
        logger = attach_request_id(app_logger, request_id)
        from app.adapters.memory.memory import tenant_context
        token = tenant_context.set(client_id or "default")
        try:
            # 1. Rutas rápidas
            routed = await self.routing.route_if_applicable(user_message, session_id, client_id, logger)
            if routed:
                import json
                yield json.dumps({"type": "chat", "response": routed.get("response", "")})
                return

            # 2. Construir prompt
            system_prompt = self.llm.get_system_prompt("tool", client_id=client_id)
            context, docs, facts = await self.context_builder.build_context(user_message, session_id, client_id)
            full_prompt = f"{system_prompt}\\n\\n<context>\\n{context}\\n</context>\\n"
            
            messages = [{"role": "system", "content": full_prompt}]
            recent_history = self.memory.get_recent_history(session_id, limit=5)
            messages.extend(recent_history)
            messages.append({"role": "user", "content": user_message})

            # 3. Stream
            buffer = ""
            is_json = False
            first_chunk = True
            
            import json
            async for chunk in self.llm.stream_chat(messages):
                if first_chunk:
                    chunk_stripped = chunk.strip()
                    if chunk_stripped.startswith("{") or chunk_stripped.startswith("```json"):
                        is_json = True
                    first_chunk = False
                    
                if is_json:
                    buffer += chunk
                else:
                    buffer += chunk
                    yield json.dumps({"type": "chunk", "text": chunk})
            
            # Si era JSON (Herramienta) lo ejecutamos al final
            if is_json:
                data = extract_json_robust(buffer)
                if data and "tool" in data:
                    res = await self.tool_executor.execute_tool(data["tool"], data.get("args", {}), session_id, client_id, request_id, logger, error_logger)
                    yield json.dumps({"type": "tool", "tool": data["tool"], "result": res})
                    return
                else:
                    # Falsa alarma, era texto que empezaba con {
                    yield json.dumps({"type": "chat", "response": buffer})
            else:
                yield json.dumps({"type": "chat", "response": buffer})
                
            self.memory.add_message(session_id, "user", user_message)
            self.memory.add_message(session_id, "assistant", buffer)

        finally:
            tenant_context.reset(token)
"""

if "async def run_stream" not in content:
    content += stream_method
    with open(orchestrator_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("run_stream added to planner_orchestrator.py")
else:
    print("run_stream already exists.")
