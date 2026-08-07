import pytest
from app.tools.client.system_tools import run_command

@pytest.mark.asyncio
async def test_safe_command_execution():
    # Comando permitido en la lista blanca
    res = await run_command(["python", "--version"])
    assert res["status"] == "ok"
    assert "Python" in res["stdout"] or "Python" in res["stderr"]

@pytest.mark.asyncio
async def test_unsafe_binary_blocked():
    # Binario no listado (ej. shutdown, rm, cat)
    res = await run_command(["cat", "some_file.txt"])
    assert res["status"] == "error"
    assert "Comando no permitido" in res["message"]

@pytest.mark.asyncio
async def test_python_inline_script_blocked():
    # python -c con inyección maliciosa
    res = await run_command(["python3", "-c", "import os; os.system('echo hack')"])
    assert res["status"] == "error"
    assert "Comando no permitido" in res["message"]
    
    res2 = await run_command("python -c \"print('hack')\"")
    assert res2["status"] == "error"
    assert "Comando no permitido" in res2["message"]

@pytest.mark.asyncio
async def test_shell_operator_injection_blocked():
    # Inyecciones con operadores
    res1 = await run_command("echo hola && echo hack")
    assert res1["status"] == "error"
    assert "Comando no permitido" in res1["message"]
    
    res2 = await run_command(["echo", "hola; rm -rf /"])
    assert res2["status"] == "error"
    assert "Comando no permitido" in res2["message"]
    
    res3 = await run_command("echo $(whoami)")
    assert res3["status"] == "error"
    assert "Comando no permitido" in res3["message"]
