"""
Cobertura de facturas.py: la vista /html (contenido verificable como texto)
y la /pdf (solo content-type + magic number %PDF — el layout visual no se
testea acá). Incluye el escape de HTML en datos cargados por el usuario y el
aislamiento por gym.
"""

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro, crear_plan, crear_membresia, crear_producto, crear_venta


def _cliente_con_gym(prefijo="fact"):
    client = nuevo_client()
    _registrar_gym(client, prefijo)
    return client


def test_factura_venta_html_muestra_producto_total_y_estado():
    client = _cliente_con_gym()
    pid = crear_producto(client, precio_venta="25.00", stock=10)
    nombre_prod = client.get(f"/productos/{pid}").json()["nombre"]
    venta = crear_venta(client, pid, cantidad=2, pago_inicial=50)

    r = client.get(f"/facturas/venta/{venta['id']}/html")
    assert r.status_code == 200, r.text
    html = r.text
    assert nombre_prod in html
    assert "$50.00" in html
    assert "Pagada" in html
    assert f"V-{venta['id']:05d}" in html


def test_factura_venta_en_abono_muestra_saldo_pendiente():
    client = _cliente_con_gym()
    pid = crear_producto(client, precio_venta="100.00", stock=5)
    venta = crear_venta(client, pid, cantidad=1, pago_inicial=30)

    html = client.get(f"/facturas/venta/{venta['id']}/html").text
    assert "Saldo pendiente" in html
    assert "$70.00" in html


def test_factura_membresia_html_muestra_plan_y_pagos():
    client = _cliente_con_gym()
    mid  = crear_miembro(client)
    plan = crear_plan(client, tipo="tiempo", duracion_dias=30, precio=45)
    memb = crear_membresia(client, mid, plan, precio_pagado=45)

    r = client.get(f"/facturas/membresia/{memb['id']}/html")
    assert r.status_code == 200, r.text
    html = r.text
    assert f"M-{memb['id']:05d}" in html
    assert "Membresía:" in html
    assert "$45.00" in html


def test_factura_escapa_html_en_notas_de_venta():
    # Las notas las escribe el usuario; si llegan crudas al HTML servido en
    # /html es un XSS almacenado. sanitizar() + escape() deben neutralizarlo.
    client = _cliente_con_gym()
    pid = crear_producto(client)
    r = client.post("/ventas/", json={
        "items":          [{"producto_id": pid, "cantidad": 1}],
        "porcentaje_iva": 0,
        "pago_inicial":   100,
        "notas":          '<script>alert("xss")</script>',
    })
    assert r.status_code == 201, r.text

    html = client.get(f"/facturas/venta/{r.json()['id']}/html").text
    assert "<script>" not in html


def test_factura_pdf_devuelve_pdf_real():
    client = _cliente_con_gym()
    pid = crear_producto(client)
    venta = crear_venta(client, pid, pago_inicial=100)

    r = client.get(f"/facturas/venta/{venta['id']}/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_factura_inexistente_da_404():
    client = _cliente_con_gym()
    assert client.get("/facturas/venta/99999/html").status_code == 404
    assert client.get("/facturas/membresia/99999/html").status_code == 404


def test_factura_de_otro_gym_da_404():
    client_a = _cliente_con_gym("factA")
    client_b = _cliente_con_gym("factB")
    pid = crear_producto(client_a)
    venta = crear_venta(client_a, pid, pago_inicial=100)

    assert client_b.get(f"/facturas/venta/{venta['id']}/html").status_code == 404
    assert client_b.get(f"/facturas/venta/{venta['id']}/pdf").status_code == 404
