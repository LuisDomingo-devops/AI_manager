from app.adapters.memory.memory import _get_connection

conn = _get_connection("test_user_refactor")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
print(f"Number of tables: {len(tables)}")
print(tables)
