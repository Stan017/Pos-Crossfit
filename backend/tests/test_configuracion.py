"""Fase 3 de cobertura: configuracion.py — datos del gimnasio, edición parcial."""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _cliente_con_gym():
    client = nuevo_client()
    payload = _registrar_gym(client, "config")
    return client, payload


def test_obtener_configuracion_devuelve_el_nombre_del_registro():
    client, payload = _cliente_con_gym()
    r = client.get("/configuracion/")
    assert r.status_code == 200
    assert r.json()["nombre"] == payload["gym_nombre"]


def test_actualizar_configuracion_parcial_no_toca_otros_campos():
    client, payload = _cliente_con_gym()
    r = client.patch("/configuracion/", json={"telefono": "0999999999"})
    assert r.status_code == 200
    body = r.json()
    assert body["telefono"] == "0999999999"
    assert body["nombre"] == payload["gym_nombre"]


def test_actualizar_configuracion_rechaza_iva_negativo():
    client, _ = _cliente_con_gym()
    r = client.patch("/configuracion/", json={"iva_default": -5})
    assert r.status_code == 422
