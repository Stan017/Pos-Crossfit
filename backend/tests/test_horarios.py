"""
Fase 2 de cobertura: horarios.py — clases, reservas y su límite de cupo
(el lock ya se prueba indirectamente vía checkin.py; acá se prueba la
regla en sí, sin concurrencia).
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro, crear_clase


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "horario")
    return client


def test_crear_clase_rechaza_hora_fin_antes_de_hora_inicio():
    client = _cliente_con_gym()
    r = client.post("/horarios/clases", json={
        "fecha": "2026-09-01", "hora_inicio": "10:00", "hora_fin": "09:00",
        "nombre": "WOD", "capacidad": 10,
    })
    assert r.status_code == 422


def test_actualizar_clase_parcial_valida_contra_hora_existente():
    """
    ClaseUpdate es parcial — si solo llega hora_inicio, la validación tiene
    que comparar contra la hora_fin que YA tenía la fila, no asumir que
    también vino en el body (routes/horarios.py:201-208).
    """
    client = _cliente_con_gym()
    clase = crear_clase(client, hora_inicio="09:00", hora_fin="10:00")

    r = client.put(f"/horarios/clases/{clase['id']}", json={"hora_inicio": "10:30"})
    assert r.status_code == 422, r.text


def test_cancelar_clase():
    client = _cliente_con_gym()
    clase = crear_clase(client)

    r = client.patch(f"/horarios/clases/{clase['id']}/cancelar")
    assert r.status_code == 204

    listado = client.get("/horarios/clases").json()
    estado = next(c["estado"] for c in listado if c["id"] == clase["id"])
    assert estado == "cancelada"


def test_eliminar_clase_sin_asistencias():
    client = _cliente_con_gym()
    clase = crear_clase(client)

    r = client.delete(f"/horarios/clases/{clase['id']}")
    assert r.status_code == 204


def test_reservar_miembro_respeta_capacidad():
    client = _cliente_con_gym()
    clase = crear_clase(client, capacidad=1)
    m1 = crear_miembro(client)
    m2 = crear_miembro(client)

    r1 = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m1})
    assert r1.status_code == 201, r1.text

    r2 = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m2})
    assert r2.status_code == 409, r2.text


def test_reservar_miembro_rechaza_clase_cancelada():
    client = _cliente_con_gym()
    clase = crear_clase(client)
    m = crear_miembro(client)
    client.patch(f"/horarios/clases/{clase['id']}/cancelar")

    r = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m})
    assert r.status_code == 409, r.text


def test_reservar_miembro_rechaza_reserva_duplicada():
    client = _cliente_con_gym()
    clase = crear_clase(client, capacidad=5)
    m = crear_miembro(client)

    r1 = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m})
    assert r1.status_code == 201

    r2 = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m})
    assert r2.status_code == 409, r2.text


def test_reservar_miembro_rechaza_miembro_inexistente():
    client = _cliente_con_gym()
    clase = crear_clase(client)

    r = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": 999999})
    assert r.status_code == 404


def test_listar_clases_cuenta_reservados():
    client = _cliente_con_gym()
    clase = crear_clase(client, capacidad=5)
    m1 = crear_miembro(client)
    m2 = crear_miembro(client)
    client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m1})
    client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m2})

    listado = client.get("/horarios/clases").json()
    encontrada = next(c for c in listado if c["id"] == clase["id"])
    assert encontrada["reservados"] == 2


def test_actualizar_reservacion_cambia_estado():
    client = _cliente_con_gym()
    clase = crear_clase(client, capacidad=5)
    m = crear_miembro(client)
    r = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m})
    reservacion_id = r.json()["id"]

    r2 = client.put(f"/horarios/reservaciones/{reservacion_id}", json={"estado": "cancelada"})
    assert r2.status_code == 200
    assert r2.json()["estado"] == "cancelada"

    # Con la reserva cancelada, ya no cuenta contra el cupo — otro miembro puede reservar.
    m2 = crear_miembro(client)
    r3 = client.post(f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": m2})
    assert r3.status_code == 201, r3.text
