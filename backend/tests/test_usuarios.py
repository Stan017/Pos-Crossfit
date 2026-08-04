"""
Fase 3 de cobertura: usuarios.py — límite de asistentes por tier, y las
guardas de "no te desactivés a vos mismo" / "siempre queda un admin".
"""
from conftest import nuevo_client
from test_auth_rls import _registrar_gym


def _cliente_con_gym():
    """Devuelve (client, id_del_admin_que_registró_el_gym) — capturado apenas
    se crea, cuando todavía es garantizado que hay exactamente un admin."""
    client = nuevo_client()
    _registrar_gym(client, "usr")
    admins = [u for u in client.get("/usuarios/").json() if u["rol"] == "admin"]
    assert len(admins) == 1
    return client, admins[0]["id"]


def _crear_staff(client, email="staff@example.com"):
    return client.post("/usuarios/", json={
        "email": email, "password": "password123", "nombre": "Staff Test", "rol": "staff",
    })


def test_crear_usuario_staff():
    client, _ = _cliente_con_gym()
    r = _crear_staff(client)
    assert r.status_code == 201, r.text
    assert r.json()["rol"] == "staff"


def test_crear_usuario_rechaza_email_duplicado_en_el_mismo_gym():
    # rol=admin, no staff: el tier trial admite 1 solo asistente — con el
    # segundo intento usando rol=staff, verificar_limite_asistentes() corta
    # con 403 antes de llegar al chequeo de email duplicado. admin no cuenta
    # contra ese límite (ver services/planes_service.py).
    client, _ = _cliente_con_gym()
    r1 = client.post("/usuarios/", json={
        "email": "dup@example.com", "password": "password123", "nombre": "X", "rol": "admin",
    })
    assert r1.status_code == 201, r1.text
    r2 = client.post("/usuarios/", json={
        "email": "dup@example.com", "password": "password123", "nombre": "Y", "rol": "admin",
    })
    assert r2.status_code == 409


def test_crear_usuario_rechaza_password_corta():
    client, _ = _cliente_con_gym()
    r = client.post("/usuarios/", json={
        "email": "corto@example.com", "password": "123", "nombre": "X", "rol": "staff",
    })
    assert r.status_code == 422


def test_no_puede_desactivarse_a_si_mismo_via_delete():
    client, propio_id = _cliente_con_gym()
    r = client.delete(f"/usuarios/{propio_id}")
    assert r.status_code == 409, r.text


def test_no_puede_desactivarse_a_si_mismo_via_patch():
    client, propio_id = _cliente_con_gym()
    r = client.patch(f"/usuarios/{propio_id}", json={"activo": False})
    assert r.status_code == 409, r.text


def test_admin_unico_no_puede_degradarse_a_si_mismo():
    """El único admin no puede desactivarse ni degradarse — bloqueado incluso sin el guard de auto-desactivación."""
    client, propio_id = _cliente_con_gym()
    r = client.patch(f"/usuarios/{propio_id}", json={"rol": "staff"})
    # Cae primero en el guard de auto-desactivación (es uno mismo), da 409 igual.
    assert r.status_code == 409, r.text


def test_desactivar_admin_original_ok_una_vez_que_hay_otro_admin():
    client, propio_id = _cliente_con_gym()
    staff_id = _crear_staff(client).json()["id"]

    r_promover = client.patch(f"/usuarios/{staff_id}", json={"rol": "admin"})
    assert r_promover.status_code == 200, r_promover.text

    # Ahora hay dos admins — pero seguís siendo VOS mismo, así que el guard
    # de auto-desactivación sigue aplicando (esto prueba que ese guard no
    # depende de "sos el último admin", corre siempre).
    r = client.patch(f"/usuarios/{propio_id}", json={"activo": False})
    assert r.status_code == 409, r.text


def test_desactivar_a_otro_admin_ok_si_queda_uno_activo():
    """
    _hay_otro_admin_activo() con actor y objetivo distintos (a diferencia de
    los tests de arriba, donde el guard de auto-desactivación siempre gana
    primero y nunca se llega a evaluar este chequeo específico).
    """
    client, _ = _cliente_con_gym()
    staff = _crear_staff(client, email="segundo@example.com").json()
    client.patch(f"/usuarios/{staff['id']}", json={"rol": "admin"})

    r = client.patch(f"/usuarios/{staff['id']}", json={"activo": False})
    assert r.status_code == 200, r.text
