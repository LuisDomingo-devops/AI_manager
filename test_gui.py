import sys
import os
from pathlib import Path

# Redirigir a client/test_gui.py
client_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "client")
sys.path.insert(0, client_dir)

from client.test_gui import config
from client.gui.app import launch

if __name__ == "__main__":
    launch(config)
