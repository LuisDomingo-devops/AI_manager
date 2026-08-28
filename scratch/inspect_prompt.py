import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()

from app.adapters.llm_client import get_system_prompt
prompt = get_system_prompt("1051b91c-993f-47bf-ade8-0da6a794ee2a", "tool")
print("=== SYSTEM PROMPT ===")
print(prompt)
