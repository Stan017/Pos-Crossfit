"""
Fase 1 de cobertura: ventas.py — stock, IVA, estado pagada/abono, reemplazo
de ítems (preservando costo extra), eliminación con restauración de stock.
costo-extra y su lock ya están cubiertos en test_ventas_concurrencia.py /
test_ventas_locks.py — no se repiten acá.
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_producto, crear_venta


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "venta")
    return client


def test_crear_venta_descuenta_stock():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="20.00", stock=10)

    crear_venta(client, producto_id, cantidad=3)

    producto = client.get(f"/productos/{producto_id}").json()
    assert producto["stock"] == 7


def test_crear_venta_rechaza_stock_insuficiente():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="20.00", stock=2)

    r = client.post("/ventas/", json={
        "items": [{"producto_id": producto_id, "cantidad": 5}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 400, r.text

    # El stock no se tocó — el rechazo fue antes de descontar.
    producto = client.get(f"/productos/{producto_id}").json()
    assert producto["stock"] == 2


def test_crear_venta_rechaza_producto_inexistente():
    client = _cliente_con_gym()
    r = client.post("/ventas/", json={
        "items": [{"producto_id": 999999, "cantidad": 1}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 404


def test_crear_venta_rechaza_sin_items():
    client = _cliente_con_gym()
    r = client.post("/ventas/", json={"items": [], "porcentaje_iva": 0})
    assert r.status_code == 400


def test_crear_venta_calcula_iva():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="100.00", stock=10)

    venta = crear_venta(client, producto_id, cantidad=1, porcentaje_iva=15)
    assert float(venta["subtotal"]) == 100.0
    assert float(venta["monto_iva"]) == 15.0
    assert float(venta["total"]) == 115.0


def test_crear_venta_pago_completo_queda_pagada():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)

    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=50)
    assert venta["estado"] == "pagada"


def test_crear_venta_pago_parcial_queda_abono():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)

    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=20)
    assert venta["estado"] == "abono"


def test_reemplazar_items_ajusta_stock():
    client = _cliente_con_gym()
    prod_a = crear_producto(client, precio_venta="10.00", stock=10)
    prod_b = crear_producto(client, precio_venta="20.00", stock=10)

    venta = crear_venta(client, prod_a, cantidad=3)  # stock A: 10 -> 7

    r = client.patch(f"/ventas/{venta['id']}/items", json={
        "items": [{"producto_id": prod_b, "cantidad": 2}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 200, r.text

    a = client.get(f"/productos/{prod_a}").json()
    b = client.get(f"/productos/{prod_b}").json()
    assert a["stock"] == 10  # restaurado
    assert b["stock"] == 8   # 10 - 2


def test_reemplazar_items_rechaza_stock_insuficiente():
    client = _cliente_con_gym()
    prod_a = crear_producto(client, precio_venta="10.00", stock=10)
    prod_b = crear_producto(client, precio_venta="20.00", stock=1)

    venta = crear_venta(client, prod_a, cantidad=1)

    r = client.patch(f"/ventas/{venta['id']}/items", json={
        "items": [{"producto_id": prod_b, "cantidad": 5}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 400, r.text


def test_reemplazar_items_preserva_costo_extra():
    """
    Los ítems de costo extra (producto_id NULL) no se tocan al reemplazar
    los de producto — ver el comentario en reemplazar_items_y_recalcular_stock
    sobre por qué se excluyen explícitamente del borrado.
    """
    client = _cliente_con_gym()
    prod_a = crear_producto(client, precio_venta="10.00", stock=10)
    prod_b = crear_producto(client, precio_venta="30.00", stock=10)

    venta = crear_venta(client, prod_a, cantidad=1, porcentaje_iva=0)
    client.post(f"/ventas/{venta['id']}/costo-extra", json={
        "descripcion": "Extra", "monto": 15,
    })

    r = client.patch(f"/ventas/{venta['id']}/items", json={
        "items": [{"producto_id": prod_b, "cantidad": 1}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 200, r.text
    actualizada = r.json()

    tipos = [i["producto_id"] for i in actualizada["items"]]
    assert prod_b in tipos
    assert None in tipos  # el costo extra sigue ahí
    assert float(actualizada["subtotal"]) == 30.0 + 15.0


def test_eliminar_venta_restaura_stock():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="10.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=4)

    r = client.delete(f"/ventas/{venta['id']}")
    assert r.status_code == 204

    producto = client.get(f"/productos/{producto_id}").json()
    assert producto["stock"] == 10


def test_eliminar_venta_rechaza_si_tiene_pagos():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="10.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=10)

    r = client.delete(f"/ventas/{venta['id']}")
    assert r.status_code == 409, r.text

    # Sigue existiendo, el stock no se restauró.
    producto = client.get(f"/productos/{producto_id}").json()
    assert producto["stock"] == 9
