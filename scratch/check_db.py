import sqlite3

def check_db(db_path):
    try:
        conn = sqlite3.connect(db_path)
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        print(f"--- {db_path} ---")
        print(f"Number of tables: {len(tables)}")
        for table in tables:
            print(f" - {table}")
    except Exception as e:
        print(f"Error reading {db_path}: {e}")

check_db('data/memory.db')
check_db('data/alfonso_default.db')
