"""
Cobertura de miembros.py — el CRUD central del sistema. Hasta ahora solo se
usaba incidentalmente como fixture de otros tests (helpers.crear_miembro);
acá se prueban sus propias reglas: duplicados por nombre y cédula, búsqueda,
update parcial con exclude_unset, desactivar/reactivar y aislamiento por gym.
"""
from datetime import date

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro, crear_plan, crear_membresia


def _cliente_con_gym(prefijo="miem"):
    client = nuevo_client()
    _registrar_gym(client, prefijo)
    return client


def _payload_miembro(nombre="Juan", apellido="Perez", **extra):
    return {
        "nombre":        nombre,
        "apellido":      apellido,
        "fecha_ingreso": str(date.today()),
        **extra,
    }


def test_crear_miembro_devuelve_201_y_todos_los_campos():
    client = _cliente_con_gym()
    r = client.post("/miembros/", json=_payload_miembro(
        email="juan@example.com", telefono="0999999999", cedula="1712345678",
    ))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["nombre"] == "Juan"
    assert body["cedula"] == "1712345678"
    assert body["activo"] is True
    assert body["membresia_activa"] is None


def test_crear_miembro_rechaza_nombre_duplicado_case_insensitive():
    client = _cliente_con_gym()
    client.post("/miembros/", json=_payload_miembro("Steffy", "Rosero"))
    r = client.post("/miembros/", json=_payload_miembro("steffy", "ROSERO"))
    assert r.status_code == 409, r.text


def test_crear_miembro_rechaza_cedula_duplicada():
    client = _cliente_con_gym()
    client.post("/miembros/", json=_payload_miembro("Ana", "Lopez", cedula="1700000001"))
    r = client.post("/miembros/", json=_payload_miembro("Otra", "Persona", cedula="1700000001"))
    assert r.status_code == 409, r.text


def test_listar_filtra_por_busqueda_y_activo():
    client = _cliente_con_gym()
    client.post("/miembros/", json=_payload_miembro("Carlos", "Andrade"))
    id_b = client.post("/miembros/", json=_payload_miembro("Berta", "Zambrano")).json()["id"]
    client.delete(f"/miembros/{id_b}")  # la desactiva

    activos = client.get("/miembros/", params={"activo": True}).json()
    assert [m["nombre"] for m in activos] == ["Carlos"]

    por_q = client.get("/miembros/", params={"q": "zambr"}).json()
    assert [m["nombre"] for m in por_q] == ["Berta"]


def test_obtener_miembro_inexistente_da_404():
    client = _cliente_con_gym()
    assert client.get("/miembros/99999").status_code == 404


def test_actualizar_parcial_no_pisa_campos_no_enviados():
    client = _cliente_con_gym()
    mid = client.post("/miembros/", json=_payload_miembro(
        "Luis", "Vega", telefono="0988888888",
    )).json()["id"]

    r = client.put(f"/miembros/{mid}", json={"email": "luis@example.com"})
    assert r.status_code == 200, r.text
    assert r.json()["email"] == "luis@example.com"
    assert r.json()["telefono"] == "0988888888"


def test_actualizar_rechaza_nombre_null_explicito():
    # nombre es NOT NULL: {"nombre": null} tiene que dar 422, no IntegrityError.
    client = _cliente_con_gym()
    mid = crear_miembro(client)
    r = client.put(f"/miembros/{mid}", json={"nombre": None})
    assert r.status_code == 422, r.text


def test_desactivar_y_reactivar_miembro():
    client = _cliente_con_gym()
    mid = crear_miembro(client)

    assert client.delete(f"/miembros/{mid}").status_code == 204
    assert client.get(f"/miembros/{mid}").json()["activo"] is False

    r = client.patch(f"/miembros/{mid}/reactivar")
    assert r.status_code == 200, r.text
    assert r.json()["activo"] is True


def test_miembro_con_membresia_vigente_la_expone_en_membresia_activa():
    client = _cliente_con_gym()
    mid  = crear_miembro(client)
    plan = crear_plan(client, tipo="clases", clases_total=10)
    crear_membresia(client, mid, plan)

    body = client.get(f"/miembros/{mid}").json()
    activa = body["membresia_activa"]
    assert activa is not None
    assert activa["plan_id"] == plan
    assert activa["clases_restantes"] == 10


def test_miembros_de_otro_gym_no_se_ven_ni_se_tocan():
    client_a = _cliente_con_gym("gymA")
    client_b = _cliente_con_gym("gymB")
    mid_a = crear_miembro(client_a, "SoloDeA")

    assert all(m["nombre"] != "SoloDeA" for m in client_b.get("/miembros/").json())
    assert client_b.get(f"/miembros/{mid_a}").status_code == 404
    assert client_b.put(f"/miembros/{mid_a}", json={"nombre": "Hackeado"}).status_code == 404
    assert client_b.delete(f"/miembros/{mid_a}").status_code == 404
