import pytest
import sqlite3
from app.utils.validators import validate_nif_nie_cif
from app.tools.server.billing_tools import create_client, update_client, delete_client, get_clients
from app.adapters.memory.memory import _get_connection

def test_nif_nie_cif_validation():
    # NIF válidos
    assert validate_nif_nie_cif("12345678Z") is True
    assert validate_nif_nie_cif("48651234R") is True
    
    # NIE válidos
    assert validate_nif_nie_cif("X1234567L") is True
    
    # CIF válidos
    assert validate_nif_nie_cif("B12345674") is True 

    # Inválidos
    assert validate_nif_nie_cif("12345678A") is False
    assert validate_nif_nie_cif("INVALID") is False
    assert validate_nif_nie_cif("") is False

@pytest.mark.asyncio
async def test_client_crud_flow():
    # Limpiamos clientes en la base de datos de test
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients")
        conn.commit()
    finally:
        conn.close()

    # 1. Crear con NIF inválido
    res = await create_client(name="Cliente Invalido", nif="11111111A", email="test@test.com")
    assert res["status"] == "error"
    assert "no es valido" in res["message"] or "no es válido" in res["message"]

    # 2. Crear con NIF válido
    res = await create_client(name="Cliente Test", nif="12345678Z", email="test@test.com", address="Calle A")
    assert res["status"] == "ok"
    
    # Obtener clientes para verificar id
    res_list = await get_clients()
    assert res_list["status"] == "ok"
    clients = res_list["clients"]
    assert len(clients) == 1
    client = clients[0]
    assert client["name"] == "Cliente Test"
    assert client["nif"] == "12345678Z"
    client_id = client["id"]

    # 3. Actualizar con NIF inválido
    res = await update_client(client_id=client_id, nif="INVALID")
    assert res["status"] == "error"

    # 4. Actualizar con NIF válido y otros campos
    res = await update_client(client_id=client_id, name="Cliente Test Modificado", email="new@test.com")
    assert res["status"] == "ok"

    res_list = await get_clients()
    client = res_list["clients"][0]
    assert client["name"] == "Cliente Test Modificado"
    assert client["email"] == "new@test.com"

    # 5. Eliminar cliente
    res = await delete_client(client_id=client_id, confirmed_by_user=True)
    assert res["status"] == "ok"

    res_list = await get_clients()
    assert len(res_list["clients"]) == 0

    # 6. Intentar eliminar cliente inexistente
    res = await delete_client(client_id=99999, confirmed_by_user=True)
    assert res["status"] == "error"
