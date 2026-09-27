import re
with open('tests/backend/integration/test_planner_orchestrator_memory.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('\'{"intent": "operational"}\',', '\'{"type": "message", "message": "operational"}\',')
content = re.sub(r'\'{"tool": "(.*?)", "args": (.*?)}\',', r'\'{"type": "tool_call", "tool_name": "\1", "tool_args": \2}\',', content)

# I also need to replace the response strings with message type, for example 'Resumen de la conversación.' doesn't matter, but the ones right after a tool do matter.
# Wait, I already know which ones are there.
content = content.replace("'He borrado ese recuerdo.',", "'{\"type\": \"message\", \"message\": \"He borrado ese recuerdo.\"}'")

with open('tests/backend/integration/test_planner_orchestrator_memory.py', 'w', encoding='utf-8') as f:
    f.write(content)
