"""
Regresión: agregar_costo_extra_y_recalcular_totales (routes/ventas.py) no
lockeaba la venta con with_for_update() — dos requests concurrentes leían el
mismo venta.subtotal viejo, y el que ganaba la carrera al commitear pisaba
el total del otro. El VentaItem de ambos quedaba guardado (se veía en la
factura), pero venta.total dejaba de sumar lo que decían sus propios ítems.

Dos threads reales, no simulados — cada uno con su propio TestClient (su
propio transporte/portal ASGI), compartiendo la cookie de sesión del mismo
admin ya logueado. threading.Barrier los sincroniza para que arranquen el
POST en el mismo instante y maximizar que se solapen de verdad a nivel de
Postgres, no solo a nivel de Python.
"""
import threading
import uuid

from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _crear_producto(client) -> int:
    r = client.post("/productos/", json={
        "nombre":       f"Prod {uuid.uuid4().hex[:6]}",
        "precio_venta": "100.00",
        "stock":        100,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_venta(client, producto_id: int) -> int:
    r = client.post("/ventas/", json={
        "items":          [{"producto_id": producto_id, "cantidad": 1}],
        "porcentaje_iva": 0,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_costo_extra_concurrente_no_pierde_ningun_monto():
    client_a = nuevo_client()
    _registrar_gym(client_a, "concurr")

    client_b = nuevo_client()
    client_b.cookies.update(client_a.cookies)  # mismo admin, sesión ya iniciada

    producto_id = _crear_producto(client_a)
    venta_id    = _crear_venta(client_a, producto_id)
    subtotal_original = float(client_a.get(f"/ventas/{venta_id}").json()["subtotal"])

    barrera = threading.Barrier(2)
    resultados = {}

    def agregar(client, monto, clave):
        barrera.wait()  # arrancan el POST juntos, a propósito
        resultados[clave] = client.post(
            f"/ventas/{venta_id}/costo-extra",
            json={"descripcion": f"Extra {clave}", "monto": monto},
        )

    t_a = threading.Thread(target=agregar, args=(client_a, 10.0, "a"))
    t_b = threading.Thread(target=agregar, args=(client_b, 20.0, "b"))
    t_a.start()
    t_b.start()
    t_a.join()
    t_b.join()

    assert resultados["a"].status_code == 201, resultados["a"].text
    assert resultados["b"].status_code == 201, resultados["b"].text

    venta_final = client_a.get(f"/ventas/{venta_id}").json()

    # El bug real: sin lock, esto daba subtotal_original + 10 O + 20, nunca
    # los dos — uno de los dos POST "ganaba" y pisaba el total del otro.
    assert float(venta_final["total"]) == subtotal_original + 10.0 + 20.0
    assert len(venta_final["items"]) == 3  # 1 del producto + 2 costo-extra
