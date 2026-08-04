"""
Regresión: registrar_checkin_y_descontar_clase (routes/checkin.py) creaba
una reserva walk-in confirmada sin chequear clase.capacidad — a diferencia
de reservar_miembro (routes/horarios.py), que sí la respeta. Un check-in
directo podía superar la capacidad que reservar_miembro ya hacía cumplir.
"""
import uuid
from datetime import date, timedelta

from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _crear_plan_por_clases(client) -> int:
    r = client.post("/planes/", json={
        "nombre":       f"Plan {uuid.uuid4().hex[:6]}",
        "tipo":         "clases",
        "clases_total": 10,
        "precio":       50,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_miembro(client, nombre: str) -> int:
    r = client.post("/miembros/", json={
        "nombre":         nombre,
        "apellido":       "Test",
        "fecha_ingreso":  str(date.today()),
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_membresia(client, miembro_id: int, plan_id: int) -> None:
    r = client.post("/membresias/", data={
        "miembro_id":     miembro_id,
        "plan_id":        plan_id,
        "fecha_inicio":   str(date.today()),
        "precio_pagado":  50,
        "metodo_pago":    "efectivo",
    })
    assert r.status_code == 201, r.text


def _crear_clase(client, capacidad: int) -> int:
    manana = date.today() + timedelta(days=1)
    r = client.post("/horarios/clases", json={
        "fecha":       str(manana),
        "hora_inicio": "09:00",
        "hora_fin":    "10:00",
        "nombre":      "WOD Test",
        "capacidad":   capacidad,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_checkin_walkin_respeta_capacidad_de_la_clase():
    client = nuevo_client()
    _registrar_gym(client, "checkincap")

    plan_id = _crear_plan_por_clases(client)
    clase_id = _crear_clase(client, capacidad=1)

    miembro_1 = _crear_miembro(client, "Primero")
    miembro_2 = _crear_miembro(client, "Segundo")
    _crear_membresia(client, miembro_1, plan_id)
    _crear_membresia(client, miembro_2, plan_id)

    r1 = client.post("/checkin/", json={"miembro_id": miembro_1, "clase_id": clase_id})
    assert r1.status_code == 201, r1.text

    # El bug real: esto pasaba con 201 sin chequear capacidad. Con la clase
    # ya en 1/1 (capacidad=1), el segundo walk-in tiene que rechazarse.
    r2 = client.post("/checkin/", json={"miembro_id": miembro_2, "clase_id": clase_id})
    assert r2.status_code == 409, r2.text
    assert "cupo" in r2.json()["detail"].lower()
