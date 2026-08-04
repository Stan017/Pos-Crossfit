"""Fase 2 de cobertura: inventario.py — vista de solo lectura sobre productos."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_producto, crear_venta


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "inv")
    return client


def test_inventario_no_muestra_productos_desactivados():
    client = _cliente_con_gym()
    activo_id = crear_producto(client)
    inactivo_id = crear_producto(client)
    client.delete(f"/productos/{inactivo_id}")

    ids = [p["id"] for p in client.get("/inventario/").json()]
    assert activo_id in ids
    assert inactivo_id not in ids


def test_inventario_busqueda_por_nombre():
    client = _cliente_con_gym()
    r = client.post("/productos/", json={
        "nombre": "Proteina Whey Especial", "precio_venta": "30.00", "stock": 5,
    })
    assert r.status_code == 201

    resultado = client.get("/inventario/", params={"q": "Whey"}).json()
    assert any(p["nombre"] == "Proteina Whey Especial" for p in resultado)

    vacio = client.get("/inventario/", params={"q": "NoExiste123"}).json()
    assert vacio == []


def test_stock_bajo_filtra_por_stock_minimo():
    client = _cliente_con_gym()
    r_bajo = client.post("/productos/", json={
        "nombre": "Stock Bajo", "precio_venta": "10.00", "stock": 2, "stock_minimo": 5,
    })
    r_ok = client.post("/productos/", json={
        "nombre": "Stock OK", "precio_venta": "10.00", "stock": 20, "stock_minimo": 5,
    })
    assert r_bajo.status_code == 201 and r_ok.status_code == 201

    resultado = client.get("/inventario/stock-bajo").json()
    ids = [p["id"] for p in resultado]
    assert r_bajo.json()["id"] in ids
    assert r_ok.json()["id"] not in ids


def test_productos_sin_movimiento_excluye_vendidos():
    client = _cliente_con_gym()
    vendido_id = crear_producto(client, stock=10)
    sin_vender_id = crear_producto(client, stock=10)
    crear_venta(client, vendido_id, cantidad=1)

    ids = [p["id"] for p in client.get("/inventario/sin-movimiento").json()]
    assert sin_vender_id in ids
    assert vendido_id not in ids


def test_productos_sin_movimiento_no_se_rompe_con_costo_extra_en_el_historial():
    """
    Ver el comentario en inventario.py sobre por qué el filtro excluye
    producto_id NULL de la subquery — un solo NULL ahí y "NOT IN" deja de
    devolver productos para todo el gym.
    """
    client = _cliente_con_gym()
    producto_id = crear_producto(client, stock=10)
    otro_id = crear_producto(client, stock=10)
    venta = crear_venta(client, producto_id, cantidad=1)
    client.post(f"/ventas/{venta['id']}/costo-extra", json={"descripcion": "Extra", "monto": 5})

    ids = [p["id"] for p in client.get("/inventario/sin-movimiento").json()]
    assert otro_id in ids
