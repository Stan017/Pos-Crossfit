"""Fase 3 de cobertura: deudas.py — vista unificada de ventas en abono y membresías con saldo."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_plan, crear_miembro, crear_membresia, crear_producto, crear_venta


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "deuda")
    return client


def test_deudas_incluye_venta_en_abono():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00")
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=20)

    deudas = client.get("/deudas/").json()
    entrada = next(d for d in deudas if d["tipo"] == "venta" and d["id"] == venta["id"])
    assert float(entrada["pendiente"]) == 30.0


def test_deudas_no_incluye_venta_pagada():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00")
    venta = crear_venta(client, producto_id, cantidad=1, pago_inicial=50)

    deudas = client.get("/deudas/").json()
    ids_venta = [d["id"] for d in deudas if d["tipo"] == "venta"]
    assert venta["id"] not in ids_venta


def test_deudas_incluye_membresia_pendiente_de_pago():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=80)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=0)

    deudas = client.get("/deudas/").json()
    entrada = next(d for d in deudas if d["tipo"] == "membresia" and d["id"] == m["id"])
    assert float(entrada["pendiente"]) == 80.0
    assert entrada["estado"] == "pendiente_pago"


def test_deudas_no_incluye_membresia_sin_saldo():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=80)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id, precio_pagado=80)

    deudas = client.get("/deudas/").json()
    ids_membresia = [d["id"] for d in deudas if d["tipo"] == "membresia"]
    assert m["id"] not in ids_membresia
