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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))  # backend/
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))         # backend/tests/

import psycopg2
import pytest

from apply_schema import aplicar_schema_de_test  # noqa: E402

import main  # noqa: E402 — recién ahora, con las env vars ya seteadas
from limiter import limiter  # noqa: E402

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
