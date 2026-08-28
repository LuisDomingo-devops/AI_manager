import pytest
from app.tools.server.billing_tools import create_product, get_products, update_product, delete_product
from app.adapters.memory.memory import _get_connection

@pytest.mark.asyncio
async def test_products_crud_flow():
    # 1. Limpiar tabla de productos para asegurar independencia del test
    conn = _get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products")
        conn.commit()
    finally:
        conn.close()

    # 2. Crear productos de prueba
    res1 = await create_product(sku="SERV-001", name="Desarrollo Backend", price=85.0, description="Precio por hora", iva_rate=21.0)
    assert res1["status"] == "ok"
    assert "registrado exitosamente" in res1["message"]

    res2 = await create_product(sku="PROD-102", name="Licencia SaaS Alfonso", price=299.0, description="Suscripción anual", iva_rate=21.0)
    assert res2["status"] == "ok"

    # Verificar restricción de unicidad de SKU
    res_dup = await create_product(sku="SERV-001", name="Desarrollo Duplicado", price=90.0)
    assert res_dup["status"] == "error"
    assert "ya existe" in res_dup["message"]

    # 3. Obtener listado de productos y verificar campos
    res_list = await get_products()
    assert res_list["status"] == "ok"
    products = res_list["products"]
    assert len(products) == 2

    p1 = next(p for p in products if p["sku"] == "SERV-001")
    assert p1["name"] == "Desarrollo Backend"
    assert p1["price"] == 85.0
    assert p1["description"] == "Precio por hora"
    assert p1["iva_rate"] == 21.0

    # 4. Actualizar producto
    res_up = await update_product(sku="SERV-001", price=95.0, description="Tarifa por hora actualizada", iva_rate=10.0)
    assert res_up["status"] == "ok"

    res_list_updated = await get_products()
    p1_updated = next(p for p in res_list_updated["products"] if p["sku"] == "SERV-001")
    assert p1_updated["price"] == 95.0
    assert p1_updated["description"] == "Tarifa por hora actualizada"
    assert p1_updated["iva_rate"] == 10.0

    # Intentar actualizar producto inexistente
    res_up_fail = await update_product(sku="PROD-NONE", price=100.0)
    assert res_up_fail["status"] == "error"

    # 5. Eliminar producto
    res_del = await delete_product(sku="SERV-001", confirmed_by_user=True)
    assert res_del["status"] == "ok"

    res_list_final = await get_products()
    assert len(res_list_final["products"]) == 1
    assert not any(p["sku"] == "SERV-001" for p in res_list_final["products"])

    # Intentar eliminar producto inexistente
    res_del_fail = await delete_product(sku="SERV-001", confirmed_by_user=True)
    assert res_del_fail["status"] == "error"
