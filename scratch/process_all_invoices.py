import asyncio
import os
import sys
from pathlib import Path

base_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(base_dir))

from app.tools.server.tax_parser_tools import parse_invoice

async def main():
    directory = Path("C:/Users/luisd/Desktop/Facturas_Para_Procesar")
    if not directory.exists():
        print(f"Directorio no encontrado: {directory}")
        return
        
    files = list(directory.iterdir())
    print(f"Encontrados {len(files)} archivos para procesar.")
    
    for f in files:
        if f.is_file():
            print(f"Procesando {f.name}...")
            result = await parse_invoice(str(f))
            print(f"Resultado: {result['message']}")

if __name__ == "__main__":
    asyncio.run(main())
