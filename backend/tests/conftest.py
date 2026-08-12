"""
Infraestructura de test: Postgres real en Docker (nunca la base de Supabase),
con los mismos roles app_backend/app_platform (NOBYPASSRLS/BYPASSRLS) que
producción — sin esto, un test de RLS correría como superusuario y daría un
verde falso, igual que nos pasó al principio con el rol "postgres" de Supabase.

Las env vars se fijan ACÁ, antes de importar cualquier módulo de la app:
database.py/auth.py leen DATABASE_URL/JWT_SECRET al nivel de módulo, una
sola vez, en el primer import — si se seteara adentro de un fixture ya sería
tarde.
"""
import os

os.environ["DATABASE_URL"]          = "postgresql://app_backend:test_only@localhost:5433/postgres"
os.environ["PLATFORM_DATABASE_URL"] = "postgresql://app_platform:test_only@localhost:5433/postgres"
os.environ["JWT_SECRET"]            = "test-secret-nunca-usar-en-produccion"
os.environ["PLATFORM_ADMIN_KEY"]    = "test-platform-key-nunca-usar-en-produccion"

import pathlib
import subprocess
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # backend/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))         # backend/tests/

import psycopg2
import pytest

from apply_schema import aplicar_schema_de_test  # noqa: E402

import main  # noqa: E402 — recién ahora, con las env vars ya seteadas
from limiter import limiter  # noqa: E402
from routes import archivos, imagenes, membresias, suscripciones  # noqa: E402

_SUPERUSER_URL = "postgresql://postgres:postgres@localhost:5433/postgres"


@pytest.fixture(scope="session", autouse=True)
def _test_db():
    compose_file = pathlib.Path(__file__).parent / "docker-compose.test.yml"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d", "--wait"],
        check=True,
    )
    aplicar_schema_de_test()
    yield
    # Sin down acá a propósito (ver docker-compose.test.yml): dejarlo arriba
    # entre corridas evita re-arrancar Postgres y re-aplicar 31 migraciones
    # en cada `pytest`. `docker compose -f backend/tests/docker-compose.test.yml
    # down` a mano cuando se quiera un container realmente nuevo.


@pytest.fixture(autouse=True)
def _estado_limpio():
    """
    Antes de CADA test: trunca todo lo que cuelga de gimnasios (CASCADE
    alcanza usuarios, miembros, membresias, ventas, etc. sin enumerarlas a
    mano) + audit_log (referencia blanda, sin FK, CASCADE no la alcanza) y
    resetea el rate limiter — 5/hora en /auth/register-gym se agotaría en
    la segunda mitad de este archivo si no se reseteara entre tests.
    """
    conn = psycopg2.connect(_SUPERUSER_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE gimnasios, audit_log RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()
    limiter.reset()
    yield


@pytest.fixture(autouse=True)
def _storage_fake(monkeypatch):
    """
    storage.py habla por HTTP con el bucket real de Supabase Storage — igual
    que con Postgres (real-de-test en Docker, nunca la DB de producción), los
    tests no deben tocar la Storage real: nada de red, nada de credenciales,
    nada de basura acumulándose en el bucket de producción en cada corrida de
    CI. Este fake en memoria reemplaza guardar_imagen/borrar_archivo/
    obtener_archivo en cada módulo que los importó por nombre (monkeypatch
    tiene que apuntar a cada uno, no a storage.py — "from storage import x"
    ya ató el nombre en el momento del import) y reproduce el mismo contrato
    (guarda bytes reales, valida la firma jpg/png, 404 si no existe) sin
    salir del proceso.
    """
    from fastapi import HTTPException

    _store = {}

    def _fake_guardar_imagen(carpeta, gym_id, archivo):
        contenido = archivo.file.read()
        if contenido.startswith(b"\x89PNG\r\n\x1a\n"):
            extension = "png"
        elif contenido.startswith(b"\xff\xd8\xff"):
            extension = "jpg"
        else:
            raise HTTPException(status_code=400, detail="Solo se aceptan imágenes JPG o PNG.")
        nombre = f"{uuid.uuid4().hex}.{extension}"
        _store[f"{carpeta}/{gym_id}/{nombre}"] = contenido
        return f"/archivos/{carpeta}/{gym_id}/{nombre}"

    def _fake_obtener_archivo(carpeta, gym_id, nombre):
        contenido = _store.get(f"{carpeta}/{gym_id}/{nombre}")
        if contenido is None:
            raise HTTPException(status_code=404, detail="Archivo no encontrado.")
        content_type = "image/png" if nombre.endswith(".png") else "image/jpeg"
        return contenido, content_type

    def _fake_borrar_archivo(url):
        partes = url.strip("/").split("/")
        if len(partes) != 4 or partes[0] != "archivos":
            return
        _, carpeta, gym_id, nombre = partes
        _store.pop(f"{carpeta}/{gym_id}/{nombre}", None)

    for modulo in (imagenes, membresias, suscripciones):
        monkeypatch.setattr(modulo, "guardar_imagen", _fake_guardar_imagen)
        monkeypatch.setattr(modulo, "borrar_archivo", _fake_borrar_archivo)
    monkeypatch.setattr(archivos, "obtener_archivo", _fake_obtener_archivo)


@pytest.fixture
def client():
    return nuevo_client()


def nuevo_client():
    """
    base_url https, no http: set_auth_cookies() pone secure=not DEBUG, y
    DEBUG es False acá a propósito (no se setea en los env vars de arriba —
    Postgres real, para que el listener de RLS esté activo). Con scheme http
    el cookie jar de TestClient nunca reenvía cookies Secure — no es un bug
    de la app, es que el "navegador" de test tiene que parecer https para
    que el comportamiento real (cookies seguras en todo lo que no es DEBUG)
    se pueda probar sin debilitarlo.
    """
    from fastapi.testclient import TestClient
    return TestClient(main.app, base_url="https://testserver")
