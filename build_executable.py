"""
SCRIPT DE COMPILACIÓN Y EMPAQUETADO A BINARIO NATIVO (.EXE) — ALFONSO AUTÓNOMO

¿QUÉ HACE?
Compila y empaqueta todo el código fuente de Alfonso en un binario ejecutable (.exe en Windows)
utilizando PyInstaller / Nuitka para proteger la propiedad intelectual, ofuscar el código
y evitar la edición o parcheo del validador de licencias local.

USO:
python build_executable.py [--mode pyinstaller|nuitka]
"""

import sys
import subprocess
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"

def build_with_pyinstaller():
    print("[*] Iniciando compilación con PyInstaller...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=AlfonsoAutonomo",
        "--onedir",
        "--clean",
        "--noconfirm",
        "--add-data=app/prompts;app/prompts",
        "--add-data=app/data;app/data",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=uvicorn.loops",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols",
        "--hidden-import=uvicorn.protocols.http",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.lifespan",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=sqlite3",
        "--hidden-import=cryptography",
        "--hidden-import=reportlab",
        "app/main.py"
    ]
    print(f"[*] Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode == 0:
        print("[+] Compilación finalizada con éxito. Ejecutable disponible en dist/AlfonsoAutonomo/")
    else:
        print("[-] Error durante la compilación con PyInstaller.", file=sys.stderr)
        return False
    return True

def build_with_nuitka():
    print("[*] Iniciando compilación a código máquina nativo C con Nuitka...")
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--output-dir=dist_nuitka",
        "--include-package=app",
        "--include-data-dir=app/prompts=app/prompts",
        "--include-data-dir=app/data=app/data",
        "--windows-company-name=Alfonso Autónomo S.L.",
        "--windows-product-name=Alfonso Autónomo",
        "--windows-file-version=5.0.0.0",
        "--windows-product-version=5.0.0.0",
        "app/main.py"
    ]
    print(f"[*] Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if result.returncode == 0:
        print("[+] Compilación C finalizada con éxito. Binario en dist_nuitka/")
    else:
        print("[-] Error durante la compilación con Nuitka.", file=sys.stderr)
        return False
    return True

if __name__ == "__main__":
    mode = "pyinstaller"
    if "--mode=nuitka" in sys.argv or "nuitka" in sys.argv:
        mode = "nuitka"

    print(f"==================================================")
    print(f"  ALFONSO AUTÓNOMO — CONSTRUCTOR DE BINARIO ({mode.upper()})")
    print(f"==================================================")
    
    if mode == "nuitka":
        build_with_nuitka()
    else:
        build_with_pyinstaller()
