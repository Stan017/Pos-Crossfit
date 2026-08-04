"""
Fase 1 de cobertura: abonos.py — pagos parciales sobre una venta en abono,
cierre automático a "pagada", y que listar_abonos solo muestre lo pendiente.
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_producto, crear_venta


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "abono")
    return client


def test_registrar_abono_reduce_saldo():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="100.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=30)  # saldo: 70

    r = client.post(f"/abonos/{venta['id']}/pagar", json={"monto": 40, "metodo": "efectivo"})
    assert r.status_code == 201, r.text

    detalle = client.get(f"/abonos/{venta['id']}").json()
    assert float(detalle["saldo"]) == 30.0
    assert float(detalle["total_pagado"]) == 70.0  # 30 inicial + 40 abono


def test_registrar_abono_que_cubre_saldo_cierra_la_venta():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="100.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=60)  # saldo: 40

    r = client.post(f"/abonos/{venta['id']}/pagar", json={"monto": 40, "metodo": "efectivo"})
    assert r.status_code == 201, r.text

    v = client.get(f"/ventas/{venta['id']}").json()
    assert v["estado"] == "pagada"


def test_registrar_abono_rechaza_monto_mayor_al_saldo():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=10)  # saldo: 40

    r = client.post(f"/abonos/{venta['id']}/pagar", json={"monto": 999, "metodo": "efectivo"})
    assert r.status_code == 400, r.text


def test_registrar_abono_rechaza_venta_ya_pagada():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=50)  # pagada de una

    r = client.post(f"/abonos/{venta['id']}/pagar", json={"monto": 1, "metodo": "efectivo"})
    assert r.status_code == 400, r.text


def test_registrar_abono_rechaza_monto_no_positivo():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=10)

    r = client.post(f"/abonos/{venta['id']}/pagar", json={"monto": 0, "metodo": "efectivo"})
    assert r.status_code == 422, r.text


def test_listar_abonos_solo_muestra_ventas_con_saldo_pendiente():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)

    venta_pagada = crear_venta(client, producto_id, cantidad=1, pago_inicial=50)
    venta_abono  = crear_venta(client, producto_id, cantidad=1, pago_inicial=10)

    abonos = client.get("/abonos/").json()
    ids = [a["venta"]["id"] for a in abonos]
    assert venta_abono["id"] in ids
    assert venta_pagada["id"] not in ids
