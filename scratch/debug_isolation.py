import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Mock environment variables like conftest.py
os.environ["ALFONSO_DB_PATH"] = "data/memory_test.db"
os.environ["GEMINI_API_KEY"] = ""
os.environ["ALFONSO_API_KEY"] = "test_api_key_default"
os.environ["ALFONSO_BRIDGE_TOKEN"] = "test_bridge_token_default"

# Import redirecting finder
import app.adapters

import app.infrastructure.database.memory.memory
mem_module = sys.modules["app.infrastructure.database.memory.memory"]

# Wrap _get_connection to print details
original_get_connection = mem_module._get_connection
def debug_get_connection(client_id=None):
    cid = (client_id or mem_module.tenant_context.get()).strip().lower()
    print(f"DEBUG: tenant_context.get()={mem_module.tenant_context.get()}, client_id={client_id}, resolved cid={cid}")
    print(f"DEBUG: mem_module.DB_PATH={mem_module.DB_PATH}, parent={mem_module.DB_PATH.parent}")
    conn = original_get_connection(client_id)
    db_file = conn.execute("PRAGMA database_list").fetchall()[0][2]
    print(f"DEBUG: opened db_file={db_file}")
    return conn
mem_module._get_connection = debug_get_connection

def run_debug():
    token_a = mem_module.tenant_context.set("tenant_a")
    print("Set tenant_a. Active:", mem_module.tenant_context.get())
    conn_a = mem_module._get_connection()
    conn_a.close()
    mem_module.tenant_context.reset(token_a)

if __name__ == "__main__":
    run_debug()
