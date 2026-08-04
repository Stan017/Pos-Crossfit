"""Fase 3 de cobertura: planes.py — validación por tipo, soft delete bloqueado por membresías activas."""

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_plan, crear_miembro, crear_membresia


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "plan")
    return client


def test_crear_plan_por_tiempo_exige_duracion_dias():
    client = _cliente_con_gym()
    r = client.post("/planes/", json={"nombre": "Mensual", "tipo": "tiempo", "precio": 40})
    assert r.status_code == 422


def test_crear_plan_por_clases_exige_clases_total():
    client = _cliente_con_gym()
    r = client.post("/planes/", json={"nombre": "Pack", "tipo": "clases", "precio": 40})
    assert r.status_code == 422


def test_crear_plan_por_tiempo_rechaza_clases_total():
    client = _cliente_con_gym()
    r = client.post("/planes/", json={
        "nombre": "Mensual", "tipo": "tiempo", "duracion_dias": 30, "clases_total": 10, "precio": 40,
    })
    assert r.status_code == 422


def test_actualizar_plan_rechaza_duracion_dias_en_plan_por_clases():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="clases", clases_total=10)

    r = client.patch(f"/planes/{plan_id}", json={"duracion_dias": 30})
    assert r.status_code == 422


def test_listar_planes_excluye_desactivados_pero_todos_los_incluye():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    client.delete(f"/planes/{plan_id}")

    activos = [p["id"] for p in client.get("/planes/").json()]
    todos   = [p["id"] for p in client.get("/planes/todos").json()]
    assert plan_id not in activos
    assert plan_id in todos


def test_desactivar_plan_rechaza_si_tiene_membresias_activas():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)
    miembro_id = crear_miembro(client)
    crear_membresia(client, miembro_id, plan_id)

    r = client.delete(f"/planes/{plan_id}")
    assert r.status_code == 409, r.text


def test_desactivar_plan_sin_membresias_activas_ok():
    client = _cliente_con_gym()
    plan_id = crear_plan(client, tipo="tiempo", duracion_dias=30)

    r = client.delete(f"/planes/{plan_id}")
    assert r.status_code == 204
