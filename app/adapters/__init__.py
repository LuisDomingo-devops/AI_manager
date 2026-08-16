import sys
import importlib

# Mapear antiguos paths de módulos a los nuevos en app/infrastructure
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
}

class RedirectingLoader:
    def __init__(self, target_module):
        self.target_module = target_module
    def create_module(self, spec):
        return self.target_module
    def exec_module(self, module):
        pass

class RedirectingFinder:
    def find_spec(self, fullname, path, target=None):
        if fullname in MAPPING:
            new_name = MAPPING[fullname]
            # Asegurar que el nuevo módulo está importado en sys.modules
            if new_name not in sys.modules:
                try:
                    importlib.import_module(new_name)
                except Exception as e:
                    # Propagar error de importación
                    raise ImportError(f"Error al importar redirect de {fullname} -> {new_name}: {str(e)}")
            # Crear alias
            target_module = sys.modules[new_name]
            sys.modules[fullname] = target_module
            
            from importlib.machinery import ModuleSpec
            return ModuleSpec(fullname, RedirectingLoader(target_module))
        return None

sys.meta_path.insert(0, RedirectingFinder())
