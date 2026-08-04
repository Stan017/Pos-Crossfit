"""
Cobertura de admin_analytics.py + services/admin_analytics_service.py: las
tres rutas del superadmin (/ping, /gyms, /resumen), el rechazo sin clave de
plataforma, y que la analítica cross-tenant realmente ve datos de más de un
gym (corre con get_db_platform, que bypassea RLS a propósito).
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro, crear_producto, crear_venta

ADMIN_HEADERS = {"X-Platform-Key": "test-platform-key-nunca-usar-en-produccion"}


def test_ping_sin_clave_es_rechazado():
    # 422: X-Platform-Key es un header requerido — FastAPI corta antes de
    # llegar a la comparación de la clave. Lo que importa es que no sea 200.
    client = nuevo_client()
    r = client.get("/admin/analytics/ping")
    assert r.status_code == 422, r.text


def test_ping_con_clave_incorrecta_es_rechazado():
    client = nuevo_client()
    r = client.get("/admin/analytics/ping", headers={"X-Platform-Key": "clave-falsa"})
    assert r.status_code in (401, 403), r.text


def test_ping_con_clave_valida_da_ok():
    client = nuevo_client()
    r = client.get("/admin/analytics/ping", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True}


def test_gyms_devuelve_una_fila_por_gym_con_sus_metricas():
    client_a = nuevo_client()
    payload_a = _registrar_gym(client_a, "anaA")
    crear_miembro(client_a)
    pid = crear_producto(client_a, precio_venta="10.00")
    crear_venta(client_a, pid, cantidad=3, pago_inicial=30)

    client_b = nuevo_client()
    payload_b = _registrar_gym(client_b, "anaB")

    r = nuevo_client().get("/admin/analytics/gyms", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    filas = {f["slug"]: f for f in r.json()}
    assert payload_a["gym_slug"].lower() in filas
    assert payload_b["gym_slug"].lower() in filas

    fila_a = filas[payload_a["gym_slug"].lower()]
    assert fila_a["miembros_total"] == 1
    assert fila_a["usuarios_admin"] == 1
    assert fila_a["ventas_mes_actual"]["cantidad"] == 1
    assert fila_a["ventas_mes_actual"]["monto"] == 30.0
    assert fila_a["saas_estado"] == "trial"

    fila_b = filas[payload_b["gym_slug"].lower()]
    assert fila_b["miembros_total"] == 0
    assert fila_b["ventas_mes_actual"]["cantidad"] == 0


def test_resumen_agrega_totales_de_toda_la_plataforma():
    client_a = nuevo_client()
    _registrar_gym(client_a, "resA")
    crear_miembro(client_a)
    crear_miembro(client_a)

    client_b = nuevo_client()
    _registrar_gym(client_b, "resB")
    crear_miembro(client_b)

    r = nuevo_client().get("/admin/analytics/resumen", headers=ADMIN_HEADERS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gyms_total"] == 2
    assert body["miembros_total"] == 3
    assert body["miembros_activos"] == 3
    assert body["usuarios_total"] == 2  # un admin por gym
    assert body["gyms_por_estado_saas"].get("trial") == 2
