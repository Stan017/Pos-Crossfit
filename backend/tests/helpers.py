"""
Helpers compartidos entre archivos de test — armar rápido "un miembro con
una membresía activa" o "una venta con stock descontado" sin repetir el
mismo bloque en cada archivo. Fase 1: ventas, membresías, abonos. Fase 2:
horarios/clases.
"""
import uuid
from datetime import date, timedelta


def crear_plan(client, tipo="clases", clases_total=10, duracion_dias=30, precio=50):
    payload = {
        "nombre": f"Plan {uuid.uuid4().hex[:6]}",
        "tipo":   tipo,
        "precio": precio,
    }
    if tipo == "clases":
        payload["clases_total"] = clases_total
    else:
        payload["duracion_dias"] = duracion_dias
    r = client.post("/planes/", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def crear_miembro(client, nombre: str = None) -> int:
    nombre = nombre or f"Miembro{uuid.uuid4().hex[:6]}"
    r = client.post("/miembros/", json={
        "nombre":        nombre,
        "apellido":      "Test",
        "fecha_ingreso": str(date.today()),
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def crear_membresia(client, miembro_id: int, plan_id: int, precio_pagado=50, fecha_inicio=None) -> dict:
    r = client.post("/membresias/", data={
        "miembro_id":    miembro_id,
        "plan_id":       plan_id,
        "fecha_inicio":  str(fecha_inicio or date.today()),
        "precio_pagado": precio_pagado,
        "metodo_pago":   "efectivo",
    })
    assert r.status_code == 201, r.text
    return r.json()


def crear_producto(client, precio_venta="100.00", stock=100) -> int:
    r = client.post("/productos/", json={
        "nombre":       f"Prod {uuid.uuid4().hex[:6]}",
        "precio_venta": precio_venta,
        "stock":        stock,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def crear_venta(client, producto_id: int, cantidad=1, porcentaje_iva=0, pago_inicial=0) -> dict:
    r = client.post("/ventas/", json={
        "items":          [{"producto_id": producto_id, "cantidad": cantidad}],
        "porcentaje_iva": porcentaje_iva,
        "pago_inicial":   pago_inicial,
    })
    assert r.status_code == 201, r.text
    return r.json()


def crear_clase(client, capacidad=20, fecha=None, hora_inicio="09:00", hora_fin="10:00") -> dict:
    r = client.post("/horarios/clases", json={
        "fecha":       str(fecha or date.today() + timedelta(days=1)),
        "hora_inicio": hora_inicio,
        "hora_fin":    hora_fin,
        "nombre":      f"Clase {uuid.uuid4().hex[:6]}",
        "capacidad":   capacidad,
    })
    assert r.status_code == 201, r.text
    return r.json()
