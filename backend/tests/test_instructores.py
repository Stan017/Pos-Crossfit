"""Fase 3 de cobertura: instructores.py — soft delete, borrado restringido al creador y sin clientes."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "instr")
    return client


def _crear_instructor(client, tipo="entrenador"):
    r = client.post("/instructores/", json={"nombre": "Coach Test", "tipo": tipo})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_crear_instructor():
    client = _cliente_con_gym()
    instructor_id = _crear_instructor(client)
    assert instructor_id is not None


def test_listar_instructores_filtra_por_activo():
    # El tier trial admite 1 solo médico/coach activo a la vez — hay que
    # desactivar el primero antes de poder crear el segundo.
    client = _cliente_con_gym()
    inactivo_id = _crear_instructor(client)
    client.patch(f"/instructores/{inactivo_id}/desactivar")
    activo_id = _crear_instructor(client)

    solo_activos = [i["id"] for i in client.get("/instructores/", params={"activo": True}).json()]
    assert activo_id in solo_activos
    assert inactivo_id not in solo_activos


def test_desactivar_instructor_es_soft_delete():
    client = _cliente_con_gym()
    instructor_id = _crear_instructor(client)

    r = client.patch(f"/instructores/{instructor_id}/desactivar")
    assert r.status_code == 204

    todos = client.get("/instructores/").json()
    encontrado = next(i for i in todos if i["id"] == instructor_id)
    assert encontrado["activo"] is False


def test_eliminar_instructor_sin_clientes_ok():
    client = _cliente_con_gym()
    instructor_id = _crear_instructor(client)

    r = client.delete(f"/instructores/{instructor_id}")
    assert r.status_code == 204

    todos = client.get("/instructores/").json()
    assert instructor_id not in [i["id"] for i in todos]


def test_reporte_instructores_incluye_los_sin_actividad_en_el_mes():
    """
    El JOIN condicional en reporte_clientes_por_instructor tiene que traer
    al instructor con 0 clientes, no excluirlo (ver el comentario en
    routes/instructores.py sobre por qué el filtro de fecha va en el JOIN).
    """
    client = _cliente_con_gym()
    instructor_id = _crear_instructor(client)

    r = client.get("/instructores/reporte", params={"mes": 1, "anio": 2020})
    assert r.status_code == 200, r.text
    filas = r.json()["instructores"]
    encontrado = next(i for i in filas if i["instructor_id"] == instructor_id)
    assert encontrado["clientes"] == 0
