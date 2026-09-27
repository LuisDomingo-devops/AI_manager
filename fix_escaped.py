import re
with open('tests/backend/integration/test_planner_orchestrator_memory.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the escaped quotes
content = content.replace("\\'", "'")

with open('tests/backend/integration/test_planner_orchestrator_memory.py', 'w', encoding='utf-8') as f:
    f.write(content)
