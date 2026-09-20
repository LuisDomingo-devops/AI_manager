import re

with open('migrations/versions/001_initial_core_schema.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'(\n\s+\))\s+conn\.execute\(\"\"\"', r'\1\n    """)\n\n    conn.execute("""', content)

if not content.strip().endswith('""")'):
    content = re.sub(r'(\n\s+\))\s*$', r'\1\n    """)\n', content)

with open('migrations/versions/001_initial_core_schema.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"opening quotes: {content.count('execute(\"\"\"')}")
print(f"closing quotes: {content.count('\"\"\")')}")
