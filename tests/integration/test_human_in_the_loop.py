import pytest
from unittest.mock import patch, MagicMock
from app.tools.server.bank_tools import run_bank_reconciliation, initiate_transfer
from app.tools.server.aeat_automation_tools import (
    fill_modelo_303_playwright, fill_modelo_130_playwright,
    fill_modelo_111_playwright, fill_modelo_115_playwright,
    fill_modelo_200_playwright, generate_modelo_303_autofill_script,
    generate_modelo_130_autofill_script, generate_modelo_111_autofill_script,
    generate_modelo_115_autofill_script, generate_modelo_202_autofill_script
)
from app.tools.server.billing_tools import delete_client, delete_product, create_client, create_product
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
async def test_bank_reconciliation_confirmation():
    # Sin confirmacion
    res = await run_bank_reconciliation(confirmed_by_user=False)
    assert res["status"] == "pending_confirmation"

    # Con confirmacion
    with patch("app.domain.services.bank_service.BankService.reconcile_matching_algorithm", return_value=[]):
        res_ok = await run_bank_reconciliation(confirmed_by_user=True)
        assert res_ok["status"] == "ok"

@pytest.mark.asyncio
async def test_initiate_transfer_confirmation():
    # Sin confirmacion
    res = await initiate_transfer(connection_id=1, recipient_name="Luis", recipient_iban="ES1234", amount=100.0, concept="test", confirmed_by_user=False)
    assert res["status"] == "pending_confirmation"

    # Con confirmacion
    with patch("app.domain.services.bank_service.BankService.initiate_transfer", return_value={"tx_id": "tx123"}):
        res_ok = await initiate_transfer(connection_id=1, recipient_name="Luis", recipient_iban="ES1234", amount=100.0, concept="test", confirmed_by_user=True)
        assert res_ok["status"] == "ok"

@pytest.mark.asyncio
async def test_aeat_models_confirmation():
    # Playwright launch helpers without confirmation
    for fill_func in [
        fill_modelo_303_playwright,
        fill_modelo_130_playwright,
        fill_modelo_111_playwright,
        fill_modelo_115_playwright
    ]:
        res = await fill_func(year=2026, quarter=3, confirmed_by_user=False)
        assert res["status"] == "pending_confirmation"

    res_200 = await fill_modelo_200_playwright(year=2026, confirmed_by_user=False)
    assert res_200["status"] == "pending_confirmation"

    # Script generators without confirmation
    for gen_func in [
        generate_modelo_303_autofill_script,
        generate_modelo_130_autofill_script,
        generate_modelo_111_autofill_script,
        generate_modelo_115_autofill_script
    ]:
        res = await gen_func(year=2026, quarter=3, confirmed_by_user=False)
        assert res["status"] == "pending_confirmation"

    res_202 = await generate_modelo_202_autofill_script(year=2026, period=1, confirmed_by_user=False)
    assert res_202["status"] == "pending_confirmation"

@pytest.mark.asyncio
async def test_delete_operations_confirmation():
    # Setup data
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM clients WHERE name='Test Client Delete'")
        cursor.execute("DELETE FROM products WHERE sku='TESTDEL'")
        cursor.execute("INSERT INTO clients (name, nif, email, address) VALUES ('Test Client Delete', '12345678Z', 'test@correo.com', 'Calle Test')")
        cursor.execute("INSERT INTO products (sku, name, price, iva_rate) VALUES ('TESTDEL', 'Test Product Delete', 50.0, 21.0)")
        conn.commit()
        
        # Obtener ID de cliente creado
        cursor.execute("SELECT id FROM clients WHERE name='Test Client Delete'")
        client_id = cursor.fetchone()["id"]
    finally:
        conn.close()

    # 1. Delete client without confirmation
    res_cli_fail = await delete_client(client_id=client_id, confirmed_by_user=False)
    assert res_cli_fail["status"] == "pending_confirmation"

    # 2. Delete product without confirmation
    res_prod_fail = await delete_product(sku="TESTDEL", confirmed_by_user=False)
    assert res_prod_fail["status"] == "pending_confirmation"

    # 3. Delete client WITH confirmation
    res_cli_ok = await delete_client(client_id=client_id, confirmed_by_user=True)
    assert res_cli_ok["status"] == "ok"

    # 4. Delete product WITH confirmation
    res_prod_ok = await delete_product(sku="TESTDEL", confirmed_by_user=True)
    assert res_prod_ok["status"] == "ok"
