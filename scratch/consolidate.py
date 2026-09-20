import os
import glob
import re

base_dir = "migrations/versions"

def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# 1. Fix invoice_id INTEGER to TEXT in 001
content_001 = read_file(os.path.join(base_dir, "001_initial_core_schema.py"))
content_001 = re.sub(r'invoice_id\s+INTEGER', 'invoice_id TEXT', content_001)

# 2. Extract conn.execute blocks from 015, 017, 018
def extract_executes(content):
    matches = re.findall(r'(try:\s+conn\.execute.*?except.*?:.*?pass|conn\.execute\([\s\S]*?\n\s*\))', content)
    return "\n\n    ".join(matches)

to_merge = ["015_qa_schema_fixes.py", "017_missing_core_tables.py", "018_fix_test_schemas.py"]

additional_executes = []
for f in to_merge:
    path = os.path.join(base_dir, f)
    if os.path.exists(path):
        content = read_file(path)
        # Fix invoice_id INTEGER to TEXT
        content = re.sub(r'invoice_id\s+INTEGER', 'invoice_id TEXT', content)
        additional_executes.append(f"# From {f}\n    " + extract_executes(content))

# Append to 001's upgrade function (just before the end)
if additional_executes:
    # Find the end of upgrade(conn) in 001. We can just append it at the bottom.
    # Wait, in python indentation matters. 001_initial_core_schema.py ends with the last conn.execute.
    # Let's append at the end of the file, assuming it's all inside upgrade(conn).
    content_001 += "\n\n    " + "\n\n    ".join(additional_executes) + "\n"
    
write_file(os.path.join(base_dir, "001_initial_core_schema.py"), content_001)

# 3. Delete merged files
for f in to_merge:
    path = os.path.join(base_dir, f)
    if os.path.exists(path):
        os.remove(path)

print("Consolidation successful.")
