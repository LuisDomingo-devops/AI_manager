import os
import sys
import importlib.util
from pathlib import Path

# Configurar variables de entorno requeridas por conftest
os.environ["ALFONSO_DB_PATH"] = "data/memory_test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ALFONSO_API_KEY"] = "test_api_key_default"
os.environ["ALFONSO_BRIDGE_TOKEN"] = "test_bridge_token_default"
os.environ["TESTING"] = "true"

# Añadir directorio raíz a sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

tests_dir = Path(__file__).resolve().parent / "tests"

print("Iniciando escaneo de imports en los archivos de test...")
for f in sorted(tests_dir.glob("test_*.py")):
    print(f"Importando: {f.name} ... ", end="", flush=True)
    try:
        spec = importlib.util.spec_from_file_location(f.stem, str(f))
        module = importlib.util.module_from_spec(spec)
        sys.modules[f.stem] = module
        spec.loader.exec_module(module)
        print("OK")
    except Exception as e:
        print(f"ERROR: {str(e)}")
print("Escaneo completado.")
