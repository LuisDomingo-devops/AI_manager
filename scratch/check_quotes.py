import re

with open('migrations/versions/001_initial_core_schema.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_quote = False
start_line = 0
for i, line in enumerate(lines):
    if 'conn.execute("""' in line:
        if in_quote:
            print(f"Error: opened at {start_line} but not closed before {i+1}")
        in_quote = True
        start_line = i + 1
    elif '""")' in line:
        in_quote = False
        
if in_quote:
    print(f"Error: opened at {start_line} but not closed at EOF")
