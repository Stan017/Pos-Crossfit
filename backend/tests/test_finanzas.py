"""Fase 3 de cobertura: finanzas.py — gastos y el resumen mensual (ingresos, costo, ganancia)."""
from datetime import date

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_producto, crear_venta


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "finanzas")
    return client


def test_crear_gasto():
    client = _cliente_con_gym()
    r = client.post("/finanzas/gastos", json={
        "categoria": "Renta", "monto": 500, "es_fijo": True,
    })
    assert r.status_code == 201, r.text
    assert float(r.json()["monto"]) == 500.0


def test_crear_gasto_rechaza_monto_no_positivo():
    client = _cliente_con_gym()
    r = client.post("/finanzas/gastos", json={"categoria": "Renta", "monto": 0})
    assert r.status_code == 422


def test_eliminar_gasto():
    client = _cliente_con_gym()
    r = client.post("/finanzas/gastos", json={"categoria": "Luz", "monto": 30})
    gasto_id = r.json()["id"]

    r2 = client.delete(f"/finanzas/gastos/{gasto_id}")
    assert r2.status_code == 204

    listado = [g["id"] for g in client.get("/finanzas/gastos").json()]
    assert gasto_id not in listado


def test_resumen_financiero_calcula_ganancia_neta():
    client = _cliente_con_gym()
    hoy = date.today()

    producto_id = crear_producto(client, precio_venta="100.00", stock=10)
    crear_venta(client, producto_id, cantidad=1, pago_inicial=100)  # ingreso: 100, costo_venta: 0 (precio_costo default 0)
    client.post("/finanzas/gastos", json={"categoria": "Renta", "monto": 40, "es_fijo": True})

    r = client.get("/finanzas/resumen", params={"mes": hoy.month, "anio": hoy.year})
    assert r.status_code == 200, r.text
    resumen = r.json()
    assert float(resumen["ingresos"]) == 100.0
    assert float(resumen["gastos_fijos"]) == 40.0
    assert float(resumen["ganancia_neta"]) == 60.0  # 100 - 0 costo - 40 gasto


def test_resumen_financiero_no_mezcla_meses():
    client = _cliente_con_gym()
    producto_id = crear_producto(client, precio_venta="50.00", stock=10)
    crear_venta(client, producto_id, cantidad=1, pago_inicial=50)

    # Un mes sin ninguna actividad no debe reflejar los ingresos de hoy
    # (anio >= 2020 por el Query(ge=2020) de la ruta).
    r = client.get("/finanzas/resumen", params={"mes": 1, "anio": 2020})
    assert r.status_code == 200, r.text
    assert float(r.json()["ingresos"]) == 0.0
