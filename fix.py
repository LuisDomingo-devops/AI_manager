import os

def fix_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    new_lines = []
    modified = False
    for line in lines:
        if "from app.utils.logger import error_logger" in line:
            new_lines.append(line.replace("from app.utils.logger import error_logger", "pass"))
            modified = True
        elif "error_logger.warning(" in line and "Excepción genérica interceptada silenciosamente." in line:
            pass
        else:
            new_lines.append(line)
            
    if modified:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"Fixed {filepath}")

for root, _, files in os.walk("app/domain/services"):
    for file in files:
        if file.endswith(".py"):
            fix_file(os.path.join(root, file))
