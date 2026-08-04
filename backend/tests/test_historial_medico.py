"""Fase 3 de cobertura: historial_medico.py — CRUD restringido a quien lo creó."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_miembro


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "histmed")
    return client


def test_crear_historial_medico():
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)

    r = client.post("/historial-medico/", json={
        "paciente_id": miembro_id, "tipo": "lesion_previa", "descripcion": "Esguince de tobillo",
    })
    assert r.status_code == 201, r.text
    assert r.json()["activa"] is True


def test_crear_historial_medico_rechaza_paciente_inexistente():
    client = _cliente_con_gym()
    r = client.post("/historial-medico/", json={
        "paciente_id": 999999, "tipo": "patologia", "descripcion": "X",
    })
    assert r.status_code == 404


def test_listar_historial_medico_de_un_paciente():
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)
    client.post("/historial-medico/", json={
        "paciente_id": miembro_id, "tipo": "operacion_previa", "descripcion": "Cirugía de rodilla",
    })

    r = client.get(f"/historial-medico/miembro/{miembro_id}")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_actualizar_historial_medico_no_permite_cambiar_tipo():
    """tipo no está en HistorialMedicoUpdate — enviarlo se ignora silenciosamente, no rompe."""
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)
    creado = client.post("/historial-medico/", json={
        "paciente_id": miembro_id, "tipo": "patologia", "descripcion": "Original",
    }).json()

    r = client.patch(f"/historial-medico/{creado['id']}", json={
        "descripcion": "Actualizada", "tipo": "lesion_previa",
    })
    assert r.status_code == 200
    assert r.json()["descripcion"] == "Actualizada"
    assert r.json()["tipo"] == "patologia"  # no cambió


def test_eliminar_historial_medico_propio():
    client = _cliente_con_gym()
    miembro_id = crear_miembro(client)
    creado = client.post("/historial-medico/", json={
        "paciente_id": miembro_id, "tipo": "patologia", "descripcion": "X",
    }).json()

    r = client.delete(f"/historial-medico/{creado['id']}")
    assert r.status_code == 204


def test_eliminar_historial_medico_de_otro_usuario_rechaza():
    client_a = nuevo_client()
    payload = _registrar_gym(client_a, "histmedb")
    miembro_id = crear_miembro(client_a)
    creado = client_a.post("/historial-medico/", json={
        "paciente_id": miembro_id, "tipo": "patologia", "descripcion": "X",
    }).json()

    # Un segundo admin del MISMO gym (usuarios.py) intenta borrar el registro del primero.
    r_usuario = client_a.post("/usuarios/", json={
        "email": "otroadmin@example.com", "password": "password123",
        "nombre": "Otro Admin", "rol": "admin",
    })
    assert r_usuario.status_code == 201, r_usuario.text

    client_b = nuevo_client()
    r_login = client_b.post("/auth/login", json={
        "email": "otroadmin@example.com", "password": "password123",
        "gym_slug": payload["gym_slug"], "vertical": "crossfit",
    })
    assert r_login.status_code == 200, r_login.text

    r = client_b.delete(f"/historial-medico/{creado['id']}")
    assert r.status_code == 403, r.text
