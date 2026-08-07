"""
Cobertura de dashboard.py + services/dashboard_service.py: KPIs en cero para
un gym recién creado, KPIs reales con datos, y el recorte de datos
financieros (revenue_mes/top_productos) para staff no-admin.
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro, crear_plan, crear_membresia, crear_producto, crear_venta


def _cliente_con_gym(prefijo="dash"):
    client = nuevo_client()
    payload = _registrar_gym(client, prefijo)
    return client, payload


def test_dashboard_gym_nuevo_todo_en_cero():
    client, _ = _cliente_con_gym()
    r = client.get("/dashboard/")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["membresias_activas"] == 0
    assert body["alertas"] == 0
    assert float(body["revenue_mes"]) == 0
    assert float(body["deuda_total"]) == 0
    assert body["top_productos"] == []
    # nuevos_mes es 0 acá porque register-gym no crea ningún Miembro.
    assert body["nuevos_mes"] == 0


def test_dashboard_refleja_membresia_venta_y_top_productos():
    client, _ = _cliente_con_gym()
    mid  = crear_miembro(client)
    plan = crear_plan(client, tipo="clases", clases_total=10, precio=50)
    crear_membresia(client, mid, plan, precio_pagado=50)
    pid = crear_producto(client, precio_venta="30.00", stock=10)
    crear_venta(client, pid, cantidad=2, pago_inicial=60)

    body = client.get("/dashboard/").json()
    assert body["membresias_activas"] == 1
    assert body["nuevos_mes"] == 1            # fecha_ingreso = hoy
    # revenue_mes ahora suma ventas POS + membresías vendidas en el mes:
    # $60 de la venta + $50 de precio_acordado de la membresía (cae al
    # precio del plan porque crear_membresia() no pasa precio_acordado).
    assert float(body["revenue_mes"]) == 110.0
    assert body["ventas_mes"] == 1
    assert float(body["deuda_total"]) == 0
    assert len(body["top_productos"]) == 1
    assert body["top_productos"][0]["unidades_vendidas"] == 2


def test_dashboard_cuenta_deuda_de_venta_en_abono():
    client, _ = _cliente_con_gym()
    pid = crear_producto(client, precio_venta="100.00", stock=5)
    crear_venta(client, pid, cantidad=1, pago_inicial=40)  # quedan $60 debiendo

    body = client.get("/dashboard/").json()
    assert float(body["deuda_total"]) == 60.0


def test_dashboard_para_staff_oculta_revenue_y_top_productos():
    client, payload = _cliente_con_gym()
    pid = crear_producto(client)
    crear_venta(client, pid, cantidad=1, pago_inicial=100)

    r_staff = client.post("/usuarios/", json={
        "email": "staff-dash@example.com", "password": "password123",
        "nombre": "Staff Dash", "rol": "staff",
    })
    assert r_staff.status_code == 201, r_staff.text

    client_staff = nuevo_client()
    r_login = client_staff.post("/auth/login", json={
        "email":    "staff-dash@example.com",
        "password": "password123",
        "gym_slug": payload["gym_slug"],
        "vertical": "crossfit",
    })
    assert r_login.status_code == 200, r_login.text

    body = client_staff.get("/dashboard/").json()
    assert body["revenue_mes"] is None
    assert body["ventas_mes"] is None
    assert body["top_productos"] == []


def test_dashboard_rechaza_mes_fuera_de_rango():
    client, _ = _cliente_con_gym()
    assert client.get("/dashboard/", params={"mes": 13, "anio": 2026}).status_code == 422
    assert client.get("/dashboard/", params={"mes": 1, "anio": 1999}).status_code == 422
