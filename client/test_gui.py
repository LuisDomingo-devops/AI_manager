import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

config = {
    'url': 'http://127.0.0.1:8000',
    'api_key': 'default_key',
    'keyword': 'alfonso',
    'device': None,
    'output_device': None,
    'model': 'tiny',
    'threshold': None,
    'debug': False,
    'gui': True
}

try:
    from gui.app import launch
    launch(config)
except Exception as e:
    import traceback
    with open("c:/Users/luisd/Desktop/Alfonso_Autonomo/gui_error.log", "w", encoding="utf-8") as f:
        f.write(traceback.format_exc())
    sys.exit(1)
