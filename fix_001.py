import subprocess

files = [
    "app/infrastructure/database/schemas/core_schema.py",
    "app/infrastructure/database/schemas/billing_schema.py",
    "app/infrastructure/database/schemas/accounting_schema.py",
    "app/infrastructure/database/schemas/ai_memory_schema.py"
]

all_code = 'import sqlite3\n\nVERSION = "001"\nDESCRIPTION = "Esquema inicial correcto"\n\ndef upgrade(conn: sqlite3.Connection) -> None:\n'

for f in files:
    res = subprocess.run(["git", "show", f"1418089800e88f5022ebb497db1fe987efc08cf5^:{f}"], capture_output=True, text=True)
    if res.returncode != 0:
        continue
    content = res.stdout
    # Extract only the conn.execute blocks
    lines = content.split('\n')
    inside_def = False
    for line in lines:
        if line.startswith('def init_'):
            inside_def = True
            continue
        if inside_def:
            if line.startswith('    conn.execute') or line.startswith('    cursor') or line.startswith('    if') or line.startswith('    #') or line.startswith('        ') or line.startswith('    except'):
                all_code += line + '\n'

with open("migrations/versions/001_initial_core_schema.py", "w", encoding="utf-8") as out:
    out.write(all_code)
