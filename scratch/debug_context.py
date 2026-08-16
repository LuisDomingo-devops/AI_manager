import sys
import os
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

# Mock environment variables like conftest.py
os.environ["ALFONSO_DB_PATH"] = "data/memory_test.db"

# Track sets to sys.modules
class TrackingDict(dict):
    def __setitem__(self, key, value):
        if "memory" in key:
            import traceback
            print(f"\n--- sys.modules SET: {key} to {id(value)} ---")
            traceback.print_stack(limit=5)
        super().__setitem__(key, value)

sys.modules = TrackingDict(sys.modules)

# Import redirecting finder
import app.adapters

# Trigger import
import app.adapters.memory.memory
