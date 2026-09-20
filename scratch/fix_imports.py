import os
import glob
import re

MAPPING = {
    "app.adapters.alfonso_bridge": "app.infrastructure.adapters.alfonso_bridge",
    "app.adapters.bank_providers": "app.infrastructure.adapters.bank_providers",
    "app.adapters.calendar_db": "app.infrastructure.database.calendar_db",
    "app.adapters.gmail_sync": "app.infrastructure.adapters.gmail_sync",
    "app.adapters.http_client": "app.infrastructure.adapters.http_client",
    "app.adapters.llm_client": "app.infrastructure.adapters.llm_client",
    "app.adapters.mail_db": "app.infrastructure.database.mail_db",
    "app.adapters.metrics": "app.infrastructure.monitoring.metrics",
    "app.adapters.tool_base": "app.infrastructure.adapters.tool_base",
    "app.adapters.tool_registry": "app.infrastructure.adapters.tool_registry",
    "app.adapters.document_customization": "app.infrastructure.database.document_customization_db",
}

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    original = content
    for old, new in MAPPING.items():
        # Replace absolute imports
        content = re.sub(rf'\b{old}\b', new, content)
        
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, _, files in os.walk('app'):
    for f in files:
        if f.endswith('.py'):
            process_file(os.path.join(root, f))
            
for root, _, files in os.walk('tests'):
    for f in files:
        if f.endswith('.py'):
            process_file(os.path.join(root, f))
            
# Clear app/adapters/__init__.py
with open('app/adapters/__init__.py', 'w', encoding='utf-8') as f:
    f.write('"""\nAdapters package (deprecated, moving to infrastructure)\n"""\n')
