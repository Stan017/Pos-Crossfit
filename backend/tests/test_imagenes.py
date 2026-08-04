"""Fase 3 de cobertura: imagenes.py — subir foto de producto, reemplazo de la anterior."""
import io

from conftest import nuevo_client
from test_auth_rls import _registrar_gym
from helpers import crear_producto

_PNG_1X1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415478da6360000002000155037f020000000049454e44"
    "ae426082"
)


def _cliente_con_gym():
    client = nuevo_client()
    _registrar_gym(client, "img")
    return client


def test_subir_imagen_producto():
    client = _cliente_con_gym()
    producto_id = crear_producto(client)

    r = client.post(
        f"/productos/{producto_id}/imagen",
        files={"file": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 200, r.text
    assert r.json()["imagen_url"].startswith("/archivos/productos/")

    producto = client.get(f"/productos/{producto_id}").json()
    assert producto["imagen_url"] == r.json()["imagen_url"]


def test_subir_imagen_rechaza_archivo_que_no_es_imagen():
    client = _cliente_con_gym()
    producto_id = crear_producto(client)

    r = client.post(
        f"/productos/{producto_id}/imagen",
        files={"file": ("nota.txt", io.BytesIO(b"esto no es una imagen"), "text/plain")},
    )
    assert r.status_code == 400, r.text


def test_subir_imagen_producto_inexistente():
    client = _cliente_con_gym()
    r = client.post(
        "/productos/999999/imagen",
        files={"file": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 404
