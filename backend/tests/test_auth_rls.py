"""
Cobertura de los flujos de auth endurecidos hoy: register-gym, login, refresh,
/me, y el aislamiento por tenant en usuarios/gimnasios (migraciones 030-032).
Es la conversión directa de la verificación manual con curl de esta sesión
en algo que corre solo — mismos casos, mismas aserciones.
"""
import uuid

from conftest import nuevo_client


def _payload_gym(prefijo: str) -> dict:
    slug = f"{prefijo}-{uuid.uuid4().hex[:8]}"
    return {
        "gym_nombre":             f"Gym {slug}",
        "gym_slug":                slug,
        "gym_email":              f"{slug}@example.com",
        "admin_nombre":           "Admin",
        "admin_apellido":         prefijo,
        "admin_fecha_nacimiento": "1990-01-01",
        "admin_email":            f"admin-{slug}@example.com",
        "admin_password":         "password123",
        "vertical":               "crossfit",
    }


def _registrar_gym(client, prefijo: str) -> dict:
    payload = _payload_gym(prefijo)
    r = client.post("/auth/register-gym", json=payload)
    assert r.status_code == 201, r.text
    return payload


# ── register-gym ────────────────────────────────────────────────────────────

def test_register_gym_crea_admin_y_setea_cookies(client):
    payload = _payload_gym("reg")
    r = client.post("/auth/register-gym", json=payload)

    assert r.status_code == 201
    body = r.json()
    assert body["nombre"] == "Admin"
    assert body["rol"] == "admin"
    assert body["gym_nombre"] == payload["gym_nombre"]
    assert "cf_access" in r.cookies
    assert "cf_refresh" in r.cookies


def test_register_gym_rechaza_slug_duplicado(client):
    payload = _registrar_gym(client, "dupslug")

    r2 = client.post("/auth/register-gym", json={
        **_payload_gym("otro"),
        "gym_slug": payload["gym_slug"],
    })
    assert r2.status_code == 409


def test_register_gym_rechaza_email_duplicado(client):
    payload = _registrar_gym(client, "dupmail")

    r2 = client.post("/auth/register-gym", json={
        **_payload_gym("otro"),
        "gym_email": payload["gym_email"],
    })
    assert r2.status_code == 409


# ── login ────────────────────────────────────────────────────────────────────

def test_login_credenciales_invalidas(client):
    payload = _registrar_gym(client, "badauth")

    r = client.post("/auth/login", json={
        "email":    payload["admin_email"],
        "password": "password-incorrecta",
        "gym_slug": payload["gym_slug"],
        "vertical": "crossfit",
    })
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciales inválidas."


def test_login_credenciales_validas(client):
    payload = _registrar_gym(client, "goodauth")

    r = client.post("/auth/login", json={
        "email":    payload["admin_email"],
        "password": payload["admin_password"],
        "gym_slug": payload["gym_slug"],
        "vertical": "crossfit",
    })
    assert r.status_code == 200
    assert r.json()["gym_nombre"] == payload["gym_nombre"]


def test_login_gym_slug_inexistente_da_401_generico(client):
    """Mismo 401 que credenciales inválidas — no debe delatar si el slug existe."""
    r = client.post("/auth/login", json={
        "email":    "nadie@example.com",
        "password": "cualquiera123",
        "gym_slug": "slug-que-no-existe",
        "vertical": "crossfit",
    })
    assert r.status_code == 401
    assert r.json()["detail"] == "Credenciales inválidas."


# ── /me y /refresh ───────────────────────────────────────────────────────────

def test_me_confirma_sesion_activa(client):
    payload = _registrar_gym(client, "me")

    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["gym_nombre"] == payload["gym_nombre"]


def test_me_sin_cookie_da_401(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_refresh_rota_el_token_y_sigue_autenticado(client):
    _registrar_gym(client, "ref")

    r = client.post("/auth/refresh")
    assert r.status_code == 200

    # El nuevo access token también sirve — confirma que rotar_refresh_token
    # resolvió bien el gym_id vía refresh_tokens.gym_id (migración 030) antes
    # de poder leer Usuario bajo RLS.
    r_me = client.get("/auth/me")
    assert r_me.status_code == 200


# ── Aislamiento por tenant (usuarios + gimnasios bajo RLS) ──────────────────

def test_usuarios_no_ve_datos_de_otro_gym():
    """
    El caso que motivó todo este bloque: dos gimnasios, cada admin debe ver
    ÚNICAMENTE su propio staff. Antes de la migración 031 esto no se podía
    ni probar (usuarios no tenía RLS); ahora es una aserción directa.
    """
    client_a = nuevo_client()
    client_b = nuevo_client()

    payload_a = _registrar_gym(client_a, "isoa")
    payload_b = _registrar_gym(client_b, "isob")

    usuarios_a = client_a.get("/usuarios/").json()
    usuarios_b = client_b.get("/usuarios/").json()

    assert [u["email"] for u in usuarios_a] == [payload_a["admin_email"]]
    assert [u["email"] for u in usuarios_b] == [payload_b["admin_email"]]


def test_configuracion_lee_el_propio_gimnasio_bajo_rls():
    """
    /configuracion/ hace Gimnasio.id == usuario.gym_id bajo get_db_tenant —
    con RLS en gimnasios (migración 032) tiene que seguir viendo su propia
    fila sin que la ruta necesitara ningún cambio.
    """
    client_a = nuevo_client()
    payload_a = _registrar_gym(client_a, "cfg")

    r = client_a.get("/configuracion/")
    assert r.status_code == 200
    assert r.json()["nombre"] == payload_a["gym_nombre"]
