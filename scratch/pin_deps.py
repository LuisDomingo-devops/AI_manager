import os
import subprocess

def run_pip_freeze():
    result = subprocess.run(['venv/Scripts/python.exe', '-m', 'pip', 'freeze'], capture_output=True, text=True)
    return result.stdout.splitlines()

freeze_lines = run_pip_freeze()
version_map = {}
for line in freeze_lines:
    if '==' in line:
        pkg, ver = line.split('==', 1)
        version_map[pkg.lower()] = ver

with open('requirements.txt', 'r', encoding='utf-8') as f:
    req_lines = f.readlines()

new_lines = []
for line in req_lines:
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        new_lines.append(line)
        continue
    
    # Extract package name ignoring extras e.g., passlib[bcrypt]>=1.7.4 -> passlib
    # Also ignore environment markers for the lookup
    pkg_part = stripped.split(';')[0].strip()
    pkg_name = pkg_part.split('[')[0].split('>')[0].split('=')[0].split('<')[0].strip().lower()
    
    if pkg_name in version_map:
        # Rebuild the line with == version
        # Keep extras if any
        extras = ''
        if '[' in pkg_part:
            extras = '[' + pkg_part.split('[')[1].split(']')[0] + ']'
            
        env_marker = ''
        if ';' in line:
            env_marker = ';' + line.split(';')[1].strip()
            
        new_line = f"{pkg_name}{extras}=={version_map[pkg_name]}{env_marker}\n"
        new_lines.append(new_line)
    else:
        new_lines.append(line)

with open('requirements.txt', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Updated requirements.txt with pinned versions.")
