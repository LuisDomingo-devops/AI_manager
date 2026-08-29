import os
import sqlite3
import shutil
from pathlib import Path
import sys

def main():
    print("Iniciando reseteo a producción...")
    
    base_dir = Path(__file__).resolve().parent.parent
    data_dir = base_dir / "data"
    
    # 1. Borrar base de datos
    db_path = data_dir / "memory.db"
    if db_path.exists():
        try:
            os.remove(db_path)
            print(f"Borrando DB: {db_path}")
        except Exception as e:
            print(f"No se pudo borrar la DB (puede que esté en uso): {e}")
        
    # 2. Borrar carpetas de archivo fiscal
    archivo_fiscal = data_dir / "archivo fiscal"
    if archivo_fiscal.exists():
        try:
            shutil.rmtree(archivo_fiscal)
            print(f"Borrando Archivo Fiscal: {archivo_fiscal}")
        except Exception as e:
            print(f"Error borrando Archivo Fiscal: {e}")
        
    archivo_fiscal.mkdir(parents=True, exist_ok=True)
    
    # 3. Borrar libros contables
    libros = data_dir / "libros_contables"
    if libros.exists():
        try:
            shutil.rmtree(libros)
            print(f"Borrando Libros Contables: {libros}")
        except Exception as e:
            print(f"Error borrando Libros Contables: {e}")
        
    libros.mkdir(parents=True, exist_ok=True)
    
    # 4. Crear DB de cero ejecutando main.py o migraciones
    sys.path.insert(0, str(base_dir))
    try:
        from app.adapters.memory.memory import _get_connection, _init_db_schema
        
        print("Inicializando nueva base de datos limpia...")
        with _get_connection() as conn:
            _init_db_schema(conn)
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        
    print("¡Reseteo completado! El sistema está vacío y listo para arrancar.")

if __name__ == "__main__":
    main()
