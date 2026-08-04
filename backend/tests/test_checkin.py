"""
Fase 2 de cobertura: checkin.py más allá de capacidad (ya en
test_checkin_capacidad.py) — descuento de clase, membresía vigente,
duplicados, clase cancelada, y reutilizar una reserva ya confirmada.
"""
from datetime import date, timedelta

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_plan, crear_miembro, crear_membresia, crear_clase


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "checkin")
    return client


def test_checkin_descuenta_clase_de_membresia_por_clases():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="clases", clases_total=10)
    miembro_id = crear_miembro(client)
    m = crear_membresia(client, miembro_id, plan_id)
    clase = crear_clase(client)

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 201, r.text

    listado = client.get("/membresias/", params={"miembro_id": miembro_id}).json()
    actualizada = next(x for x in listado if x["id"] == m["id"])
    assert actualizada["clases_usadas"] == 1


def test_checkin_no_descuenta_clase_en_plan_por_tiempo():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)
    clase = crear_clase(client)

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 201, r.text


def test_checkin_rechaza_sin_membresia():
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)
    clase = crear_clase(client)

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 409, r.text


def test_checkin_rechaza_sin_clases_disponibles():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="clases", clases_total=1)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)
    clase_1 = crear_clase(client)
    clase_2 = crear_clase(client)

    r1 = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase_1["id"]})
    assert r1.status_code == 201

    r2 = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase_2["id"]})
    assert r2.status_code == 409, r2.text


def test_checkin_rechaza_duplicado_en_la_misma_clase():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)
    clase = crear_clase(client)

    r1 = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r1.status_code == 201

    r2 = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r2.status_code == 409, r2.text


def test_checkin_rechaza_clase_cancelada():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)
    clase = crear_clase(client)
    client.patch(f"/horarios/clases/{clase['id']}/cancelar")

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 409, r.text


def test_checkin_usa_reserva_existente_en_vez_de_crear_otra():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)
    clase = crear_clase(client, capacidad=5)

    reserva = client.post(
        f"/horarios/clases/{clase['id']}/reservaciones", json={"miembro_id": miembro_id}
    ).json()

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 201, r.text
    assert r.json()["reservacion_id"] == reserva["id"]

    reservaciones = client.get(f"/horarios/clases/{clase['id']}/reservaciones").json()
    assert len(reservaciones) == 1  # no se creó una segunda


def test_checkin_rechaza_membresia_ya_vencida_al_crearla():
    """
    crear_membresia sincroniza el estado apenas se crea — con fecha_inicio
    en el pasado y una duración corta, fecha_fin ya pasó desde el momento
    cero, así que la membresía nace con estado "vencida" en DB. Esto pega
    contra el filtro Membresia.estado.in_(_ESTADOS_VIGENTES_CHECKIN) de
    checkin.py (nunca la encuentra como candidata) — NO contra el chequeo
    específico de fecha_fin vencida más abajo en la misma ruta (ese es para
    una membresía que estaba vigente en DB y venció sola, sin que nadie la
    tocara desde entonces; no se puede reproducir sin viajar en el tiempo
    dentro del test). Ambos caminos dan 409, la diferencia es interna.
    """
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=1)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id, fecha_inicio=date.today() - timedelta(days=5))
    clase = crear_clase(client)

    r = client.post("/checkin/", json={"miembro_id": miembro_id, "clase_id": clase["id"]})
    assert r.status_code == 409, r.text
