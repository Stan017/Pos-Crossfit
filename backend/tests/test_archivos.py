"""
Fase 3 de cobertura: archivos.py — servir un comprobante/foto exige que el
gym_id de la URL coincida con el del usuario logueado.
"""
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
    _registrar_gym(client, "arch")
    return client


def _subir_imagen(client) -> str:
    """Sube una foto de producto real y devuelve su imagen_url (/archivos/productos/<gym_id>/<hash>.png)."""
    producto_id = crear_producto(client)
    r = client.post(
        f"/productos/{producto_id}/imagen",
        files={"file": ("foto.png", io.BytesIO(_PNG_1X1), "image/png")},
    )
    assert r.status_code == 200, r.text
    return r.json()["imagen_url"]


def test_servir_archivo_rechaza_carpeta_invalida():
    client = _cliente_con_gym()
    r = client.get("/archivos/carpeta-rara/algun-gym/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png")
    assert r.status_code == 404


def test_servir_archivo_rechaza_nombre_con_path_traversal():
    client = _cliente_con_gym()
    r = client.get("/archivos/productos/algun-gym/..%2F..%2Fetc%2Fpasswd")
    assert r.status_code == 404


def test_servir_archivo_rechaza_gym_id_ajeno():
    client = _cliente_con_gym()
    # Nombre con forma válida (32 hex + extensión) pero gym_id de otro tenant —
    # tiene que rechazarse por el gym_id, no llegar siquiera a buscar el archivo.
    r = client.get("/archivos/productos/00000000-0000-0000-0000-000000000000/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png")
    assert r.status_code == 403


def test_servir_archivo_inexistente_da_404():
    client = _cliente_con_gym()
    url_real = _subir_imagen(client)
    gym_id_real = url_real.split("/")[3]

    r = client.get(f"/archivos/productos/{gym_id_real}/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png")
    assert r.status_code == 404


def test_servir_archivo_real_funciona():
    client = _cliente_con_gym()
    url_real = _subir_imagen(client)

    r = client.get(url_real)
    assert r.status_code == 200
    assert r.headers["content-type"] in ("image/png", "application/octet-stream")
